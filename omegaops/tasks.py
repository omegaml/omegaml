from celery import Task, shared_task
from celery.signals import worker_process_init
from celery.utils.log import get_task_logger
from django.contrib.auth.models import User
from omegaml.client.auth import AuthenticationEnv
from pymongo.errors import ConnectionFailure
from random import random
from time import sleep

import omegaops as omops
from landingpage.models import DEPLOY_COMPLETED, ServicePlan
from omegaops.celeryapp import app
from omegaops.util import enforce_logging_format, retry
from paasdeploy.models import ServiceDeployConfiguration, ServiceDeployTask, ServiceDeployCommand
from paasdeploy.tasks import deploy

logger = get_task_logger(__name__)


class BaseLoggingTask(Task):
    """
    Base class to route cloud tasks to a separate queue
    Acquires 'omops' omega for tasks
    """
    queue = 'omegaops'
    _om = None
    _events = None

    def __init__(self):
        self._in_eager_logging = False

    @property
    def events(self):
        # return the collection
        if BaseLoggingTask._events is None:
            BaseLoggingTask._events = self.om.datasets.collection('events')
        return BaseLoggingTask._events

    @property
    def om(self):
        import omegaml as default_om
        try:
            _om = self._get_authorized_om()
        except Exception as e:
            _om = default_om
        return _om

    def _get_authorized_om(self):
        # initialize only once
        if BaseLoggingTask._om is None:
            omops_user = User.objects.get(username='omops')
            auth_env = AuthenticationEnv.secure()
            BaseLoggingTask._om = om = auth_env.get_omega_from_apikey(omops_user.username, omops_user.api_key.key)
            # ensure the dataset is created and the db connection exists
            if om.datasets.metadata('events') is None:
                coll = om.datasets.collection('events')
                om.datasets.put({'initial_entry': True}, 'events')

                initial = coll.find_one()
                coll.delete_one(initial)
            else:
                om.datasets.collection('events').find_one()
        return BaseLoggingTask._om


@shared_task
def deploy_user_service(task_id=None, **kwargs):
    # this is a paasdeploy task, gets called by omops
    task = ServiceDeployTask.objects.get(pk=task_id)
    deployment = task.deployment
    user = task.command.user
    params = task.command.params
    deploy_vhost = ('vhost=yes' in params)
    password = User.objects.make_random_password(length=36)
    config = omops.add_user(user, password, deploy_vhost=deploy_vhost)
    deployment.settings = config
    deployment.text = 'userid {user.username}<br>apikey {user.api_key.key}'
    deployment.save()


@shared_task
def user_signup(task_id=None, **kwargs):
    # deploy omegaml for this user
    task = ServiceDeployTask.objects.get(pk=task_id)
    user = task.command.user
    # -- issue command to deploy omegaml
    plan = ServicePlan.objects.get(name='omegaml')
    ServiceDeployCommand.objects.create(offering=plan,
                                        user=user,
                                        phase='install')


@shared_task
def deploy_user_worker(user_id):
    """
    Deploy a new worker instance for a specific user
    :return:
    """
    user = User.objects.get(pk=user_id)
    plan = ServicePlan.objects.get(name='omegaml-worker')
    deploy_config = ServiceDeployConfiguration.get(plan=plan)
    text = 'k8 worker'
    config = 'the config vars'
    deplm = user.services.create(user=user,
                                 text=text,
                                 offering=plan,
                                 settings=config)
    deploy(deploy_config.specs, 'omegaml-worker', )
    omops.complete_service_deployment(deplm, DEPLOY_COMPLETED)


@shared_task
def run_user_scheduler():
    """
    for every user run the user-specific execute_scripts

    TODO this is hack to get this working. Will be replaced with a proper solution, https://github.com/omegaml/omegaml-enterprise/issues/117
    """
    from omegaee import eedefaults

    def schedule_for_user(user, qualifier, view):
        # get an omega instance configured to the user's specifics and send task to user's worker
        logger.info(f'scheduling jobs for user {user} qualifier {qualifier}')
        try:
            auth_env = AuthenticationEnv.secure()
            user_om = auth_env.get_omega_from_apikey(user.username, user.api_key.key,
                                                     qualifier=qualifier, view=view)
            execute_scripts = user_om.runtime.task('omegaml.notebook.tasks.execute_scripts')
            execute_scripts.apply_async()
        except Exception as e:
            logger.error(f'error scheduling for {user}, exception {e}')
        else:
            del execute_scripts
            del user_om
        # avoid excessive task bursts on rabbitmq
        sleep(1)

    users = User.objects.filter(is_active=True, groups__name__in=['scheduler'])
    view = eedefaults.OMEGA_SERVICES_INCLUSTER
    for user in users:
        settings = user.services.get(offering__name='omegaml').settings or {}
        for qualifier in settings.get('qualifiers', {}).keys():
            # enable group qualifiers to be used as scheduler accounts
            if user.username.startswith('G'):
                group = user.username[1:]
                qualifier = f'{group}:{qualifier}'
            schedule_for_user(user, qualifier, view)



@shared_task(bind=True)
def ensure_user_broker_ready(self, *args, **kwargs):
    """
    for every user (re-)create the vhost if it does not exist

    TODO: this is hack to work with unpersisted rabbitmq backends. remove in favor of persisted rabbitmq
    """
    users = User.objects.filter(is_active=True)
    for user in users:
        if user.username in ['omops']:
            # shovels to itself cause endless forwarding with increasing message volumes
            # no shovel to itself
            continue
        try:
            user_settings = user.services.get(offering__name='omegaml').settings
        except:
            continue
        if user_settings.get('version') != 'v3':
            continue
        for qualifier, cnx_config in user_settings.get('qualifiers', {}).items():
            if 'brokervhost' in cnx_config:
                print("recreating vhost {cnx_config[brokervhost]}...".format(**locals()))
                try:
                    omops.add_user_vhost(cnx_config['brokervhost'],
                                         cnx_config['brokeruser'],
                                         cnx_config['brokerpassword'])
                    # TODO rethink shovel concept (was supposed to collect service usage messages)
                    # omops.create_ops_forwarding_shovel(user)
                except Exception as e:
                    logger.error(f'error recreating user {user} vhost due to {e}')
                    # avoid excessive task bursts on rabbitmq
                sleep(.1 + random())


@app.task(base=BaseLoggingTask, bind=True)
def log_event_task(self, log_data):
    @retry(ConnectionFailure)
    def do(self, log_data):
        if not self._in_eager_logging:
            # check is to avoid endless logging calls due to, in eager mode,
            # 1. self.om triggering a request to /api/config
            # 2. which triggers the middleware to call log_event_task
            # 3. starts at 1 again (note in eager mode 2 did not return yet)
            # if not _in_eager_logging = there is no pending self.om call, so fine
            # if we run distributed, not an issue. worst case there are two
            # log calls but since they run async it won't be endless (unless
            # self.om is always None, which should not happen)
            self._in_eager_logging = True if self.request.is_eager else False
            try:
                log_data = enforce_logging_format(log_data)
            except:
                log_data['log_format_error'] = True
            # we must not fail, making sure _in_eager_logging gets reset
            try:
                # perform a fast path of self.om.datasets.put(log_data, 'events')
                # this is 20x faster
                self.events.insert({'data': log_data})
            finally:
                self._in_eager_logging = False

    do(self, log_data)

# disabled due to initialisation issue at startup
# @worker_init.connect
# def initialise_omega_connection(*args, **kwargs):
#     BaseLoggingTask().events


@worker_process_init.connect
def fix_multiprocessing(**kwargs):
    # allow celery to start sub processes
    # this is required for sklearn joblib unpickle support
    # issue see https://github.com/celery/billiard/issues/168
    # fix source https://github.com/celery/celery/issues/1709
    from multiprocessing import current_process
    try:
        current_process()._config
    except AttributeError:
        current_process()._config = {'semprefix': '/mp'}
