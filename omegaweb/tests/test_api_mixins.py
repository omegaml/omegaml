from django.contrib.auth.models import User
from django.test import TestCase
from tastypie.exceptions import BadRequest
from tastypie.test import ResourceTestCaseMixin
from unittest.mock import patch, MagicMock


class TestApiMixins(ResourceTestCaseMixin, TestCase):

    def setUp(self):
        super().setUp()
        # setup django user
        self.username = username = 'test'
        self.email = email = 'test@omegaml.io'
        self.password = password = 'password'
        self.user = User.objects.create_user(username, email, password)
        self.apikey = self.user.api_key.key

    def get_credentials(self):
        return self.create_apikey(self.username, self.apikey)

    def url(self, pk=None, action=None, query=None):
        url = '/api/v1/model/'
        if pk is not None:
            url += '{pk}/'.format(**locals())
        if action is not None:
            url += '{action}/'.format(**locals())
        if query is not None:
            url += '?{query}'.format(**locals())
        return url

    def test_bucket(self):
        """ test OmegaResourceMixin.get_omega returns Omega by Bucket header"""
        def mock_bucket(self, key):
            # this raises a BadRequest to get a json response from the API
            # there is no actual semantics to the error
            raise BadRequest(key)

        def assertBucketIs(expected, **headers):
            # simulate an API call
            # -- only interested in Omega()[bucket] being called
            resp = self.api_client.get(self.url('mymodel'),
                                       authentication=self.get_credentials(),
                                       **headers)
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(resp.json()['error'], expected)

        with patch('omegaweb.resources.omegamixin.get_omega_for_user') as omega_get:
            MockOmega = MagicMock()
            MockOmega.__getitem__ = mock_bucket
            omega_get.return_value = MockOmega
            assertBucketIs('None')
            assertBucketIs('other', HTTP_BUCKET='other')

    def test_qualifier(self):
        """ test OmegaResourceMixin.get_omega returns Omega by Qualifier header"""
        def mock_client_config(*args, qualifier=None, **kwargs):
            # this raises a BadRequest to get a json response from the API
            # there is no actual semantics to the error
            qualifier = qualifier or 'default'
            raise BadRequest(qualifier)

        def assertQualifierIs(expected, **headers):
            # simulate an API call
            # -- only interested in get_client_config being called with a
            #    valid qualifier= kwarg
            resp = self.api_client.get(self.url('mymodel'),
                                       authentication=self.get_credentials(),
                                       **headers)
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(resp.json()['error'], expected)

        with patch('omegaops.get_client_config') as client_config:
            client_config.side_effect = mock_client_config
            assertQualifierIs('default')
            assertQualifierIs('other', **dict(HTTP_QUALIFIER='other'))
            with self.assertRaises(AssertionError):
                assertQualifierIs('default', **dict(HTTP_QUALIFIER='other'))


