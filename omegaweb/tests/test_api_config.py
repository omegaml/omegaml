from landingpage.models import ServicePlan

from django.contrib.auth.models import User
from tastypie.test import ResourceTestCase
from omegaops import add_service_deployment, get_client_config


class ClientConfigResourceTests(ResourceTestCase):

    def setUp(self):
        ResourceTestCase.setUp(self)
        # setup a user including a (fake, no actual mongodb) config
        self.username = username = 'test@omegaml.io'
        self.email = email = 'test@omegaml.io'
        self.password = password = 'password'
        self.user = User.objects.create_user(username, email, password)
        ServicePlan.objects.create(name='omegaml')
        self.config = {
            'dbname': 'testdb',
            'username': self.user.username,
            'password': 'foobar',
        }
        add_service_deployment(self.user, self.config)

    def tearDown(self):
        ResourceTestCase.tearDown(self)

    def url(self, pk=None, query=None):
        url = '/api/v1/config/'
        if pk is not None:
            url += pk + '/'
        if query is not None:
            url += '?{query}'.format(**locals())
        return url

    def credentials(self):
        return self.create_apikey(self.user.username, self.user.api_key.key)

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