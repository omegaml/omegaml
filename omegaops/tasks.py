from celery import shared_task
from django.contrib.auth.models import User
from landingpage.models import DEPLOY_COMPLETED, ServicePlan
from paasdeploy.models import ServiceDeployConfiguration
from paasdeploy.tasks import deploy

import omegaops as omops


@shared_task
def deploy_user_service(user_id):
    user = User.objects.get(pk=user_id)
    password = User.objects.make_random_password(length=36)
    config = omops.add_user(user, password)
    deplm = omops.add_service_deployment(user, config)
    omops.complete_service_deployment(deplm, DEPLOY_COMPLETED)


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
