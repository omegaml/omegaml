from django.contrib.auth.models import User, Group
from django.test import TestCase
from tastypie.authentication import ApiKeyAuthentication
from tastypie.serializers import Serializer
from tastypie.test import ResourceTestCaseMixin
from tastypie.throttle import BaseThrottle
from unittest.mock import patch

from landingpage.authz import RolePermissionsAuthorization
from landingpage.models import PermissionedResource
from landingpage.permutil import PermissionUtil
from omegaops import add_service_deployment, get_client_config
from omegaweb.resources.clientconfig import ClientConfigResource


class ClientConfigResourceTests(ResourceTestCaseMixin, TestCase):
    fixtures = ['landingpage']

    def setUp(self):
        super(ClientConfigResourceTests, self).setUp()
        self.create_user()
        self.create_admin_user()

    def create_user(self):
        # setup a user including a (fake, no actual mongodb) config
        self.username = username = 'testuser'
        self.email = email = 'test@omegaml.io'
        self.password = password = 'password'
        self.user = User.objects.create_user(username, email, password)
        self.config = {
            'version': 'v3',
            'services': {
                'notebook': {
                    'url': None,
                }
            },
            'qualifiers': {
                # TODO simplify -- use a more generic user:password@service/selector format
                'default': {
                    'mongodbname': 'foobar',
                    'mongouser': 'foo',
                    'mongopassword': password,
                }
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
            'version': 'v3',
            'services': {
                'notebook': {
                    'url': None,
                }
            },
            'qualifiers': {
                # TODO simplify -- use a more generic user:password@service/selector format
                'default': {
                    'mongodbname': 'admintestdb',
                    'mongouser': self.admin_username,
                    'mongopassword': 'adminfoobar',
                }
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

    def credentials(self, user=None):
        user = user or self.user
        return self.create_apikey(user.username, user.api_key.key)

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
        resp = self.api_client.get(self.url(query='user=testuser'), authentication=auth)
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertIn('objects', data)
        service_config = data['objects'][0]['data']
        # get expected config from omegaops and compare
        actual_config = get_client_config(self.user)
        self.assertDictEqual(service_config, actual_config)

    def test_get_config_by_permission(self):
        """
        test client config is only accessible when permissioned
        """
        # set up permissions
        res = PermissionedResource.objects.create(uri='/api/v1/config/', actions='list', methods='get')
        Group.objects.create(name='service_user')
        res.allow('service_user')
        user = self.user  # User.objects.create_user('john', 'john@example.com')
        with patch.object(ClientConfigResource, '_meta') as config_api_meta:
            # mock the api meta
            # -- we do it like this because we don't have a way to set the meta on the actual resource
            config_api_meta.authentication = ApiKeyAuthentication()
            config_api_meta.authorization = RolePermissionsAuthorization()
            config_api_meta.list_allowed_methods = ['get']
            config_api_meta.throttle = BaseThrottle()
            config_api_meta.serializer = Serializer()
            # get config from api
            # -- expect failure (user is not member of service_user)
            auth = self.credentials(user=user)
            resp = self.api_client.get(self.url(), authentication=auth)
            self.assertEqual(resp.status_code, 401)
            # get config from api
            # -- expect works ok (user is member of service_user)
            PermissionUtil.assign_role(self.user, 'service_user')
            auth = self.credentials(user=user)
            resp = self.api_client.get(self.url(), authentication=auth)
            self.assertHttpOK(resp)
            # remove permission
            # -- expect failure (user is not member of service_user)
            res.deny('service_user')
            auth = self.credentials(user=user)
            resp = self.api_client.get(self.url(), authentication=auth)
            self.assertEqual(resp.status_code, 401)

    def test_get_invalid_config(self):
        """
        test useful response in case of invalid request
        """
        # get config from api
        auth = self.credentials()
        resp = self.api_client.get(self.url(query='qualifier=None'), authentication=auth)
        self.assertHttpOK(resp)
        resp = self.api_client.get(self.url(), authentication=auth,
                                   headers={'Qualifier': str(None)})
        self.assertHttpBadRequest(resp)
