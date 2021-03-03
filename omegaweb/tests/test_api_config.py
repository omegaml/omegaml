from landingpage.models import ServicePlan

from django.contrib.auth.models import User
from tastypie.test import ResourceTestCaseMixin
from omegaops import add_service_deployment, get_client_config


class ClientConfigResourceTests(ResourceTestCaseMixin):
    def setUp(self):
        super(ClientConfigResourceTests, self).setUp()
        ServicePlan.objects.create(name='omegaml')
        self.create_user()
        self.create_admin_user()

    def create_user(self):
        # setup a user including a (fake, no actual mongodb) config
        self.username = username = 'test@omegaml.io'
        self.email = email = 'test@omegaml.io'
        self.password = password = 'password'
        self.user = User.objects.create_user(username, email, password)
        self.config = {
            'default': {
                'dbname': 'testdb',
                'username': self.user.username,
                'password': 'foobar',
            }
        }
        add_service_deployment(self.user, self.config)

    def create_admin_user(self):
        # setup a user including a (fake, no actual mongodb) config
        self.admin_username = username = 'admin@omegaml.io'
        self.admin_email = email = 'admin@omegaml.io'
        self.admin_password = password = 'password'
        self.admin_user = User.objects.create_user(username, email, password)
        self.admin_user.is_staff = True
        self.admin_user.save()
        self.admin_config = {
            'default': {
                'dbname': 'admintestdb',
                'username': self.admin_username,
                'password': 'foobar',
            }
        }
        add_service_deployment(self.admin_user, self.admin_config)

    def tearDown(self):
        super(ClientConfigResourceTests, self).tearDown()

    def url(self, pk=None, query=None):
        url = '/api/v1/config/'
        if pk is not None:
            url += pk + '/'
        if query is not None:
            url += '?{query}'.format(**locals())
        return url

    def credentials(self):
        return self.create_apikey(self.user.username, self.user.api_key.key)

    def admin_credentials(self):
        return self.create_apikey(self.admin_user.username, self.admin_user.api_key.key)

    def test_get_config(self):
        """
        test the client config is real
        """
        # get config from api
        auth = self.credentials()
        resp = self.api_client.get(self.url(), authentication=auth)
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertIn('objects', data)
        service_config = data['objects'][0]['data']
        # get expected config from omegaops and compare
        actual_config = get_client_config(self.user)
        self.assertDictEqual(service_config, actual_config)

    def test_get_config_as_admin(self):
        """
        test any user can get queried by admin
        """
        # get config from api
        auth = self.admin_credentials()
        resp = self.api_client.get(self.url(query='user=test@omegaml.io'), authentication=auth)
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertIn('objects', data)
        service_config = data['objects'][0]['data']
        # get expected config from omegaops and compare
        actual_config = get_client_config(self.user)
        self.assertDictEqual(service_config, actual_config)
