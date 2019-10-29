from django.contrib.auth.models import User
from django.core.management import call_command
from mock import Mock
from tastypie.test import ResourceTestCase

from landingpage.models import ServicePlan
from omegaml import Omega
from omegaml.tests.util import OmegaTestMixin
from omegaops import get_client_config, tasks
from omegaweb.middleware import EventsLoggingMiddleware


class EventsLoggingTests(OmegaTestMixin, ResourceTestCase):
    def setUp(self):
        super(EventsLoggingTests, self).setUp()
        # setup omega credentials
        # FIXME refactor to remove dependency to landingpage (omegaweb should
        # have an injectable config module of sorts)
        ServicePlan.objects.create(name='omegaml')
        # setup test omega
        call_command('omsetupuser', username='omops', staff=True,
                     apikey='686ae4620522e790d92009be674e3bdc0391164f')
        self.omops_user = User.objects.get(username='omops')
        config = get_client_config(self.omops_user)
        # auth = (omops_user.username, omops_user.api_key.key, 'default')
        # auth_env = load_class(settings.OMEGA_AUTH_ENV)
        self.om = Omega(mongo_url=config.get('OMEGA_MONGO_URL'))
        self.middleware = EventsLoggingMiddleware()
        self.request = Mock()
        self.clean()

    def test_logging_middleware_process_request(self):
        self.assertIsNone(self.middleware.process_request(self.request))
        self.assertTrue(hasattr(self.request, 'start_dt'))

    def test_log_event_data(self):
        """
        test events logging task
        """
        from omegaops.tasks import log_event_task

        request_log = {
            'start_dt': '2019-10-16T14:41:54.897806+00:00', 
            'end_dt': '2019-10-16T14:41:54.921061+00:00', 
            'user': 'jyadmin',
            'kind': 'request', 
            'client_ip': '127.0.0.1', 
            'server_ip': '172.18.0.4', 
            'action': 'request', 
            'data': {
                'request_absolute_path': '/api/v1/dataset/', 
                'request_uri': '/api/v1/dataset/', 
                'request_method': 'GET', 
                'request_app_name': '', 
                'request_namespaces': [], 
                'request_url_name': 'api_dispatch_list',
                'request_resource_name': 'dataset'
                }, 
            'status': 200
        }
        log_event_task.s(request_log).apply()
        events = self.om.datasets.get('events')
        self.assertIsNotNone(events)
        self.assertEquals(len(events), 1)
        self.assertEquals(request_log, events[0])

        # Test broken log format is marked as such
        task_log = {
            'start_dt': '2019-10-16T15:15:41.740389', 
            'end_dt': '2019-10-16T15:15:42.336744',
            'user': 'jyadmin', 
            #'kind': 'task', 
            'client_ip': '', 
            'server_ip': '172.18.0.4', 
            'action': 'task', 
            'data': {
                'task_id': 'fef2c74d-e772-4e22-88e2-e0ebbb89eb94'}, 
            'status': 'SUCCESS'
        }
        log_event_task.s(task_log).apply()
        # we should have two events now
        events = self.om.datasets.get('events')
        self.assertEquals(len(events), 2)
        self.assertEquals(sum(1 if e.get('log_format_error') else 0
                              for e in events), 1)
