from __future__ import absolute_import

import hashlib
from allauth.account.utils import sync_user_email_addresses
from django.contrib.auth.models import User
from django.test import TestCase
from jwt_auth.exceptions import AuthenticationFailed

from omegaee.runtimes.auth import JWTOmegaRuntimeAuthentation
from omegaml import Omega
from omegaml import _base_config
from omegaml.client.auth import OmegaRuntimeAuthentication, AuthenticationEnv
from omegaml.util import delete_database, settings
from omegaweb.tests.util import OmegaResourceTestMixin

prev_auth_env = getattr(_base_config, 'OMEGA_AUTH_ENV', None)


class AuthenticatedRuntimeTests(OmegaResourceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        delete_database()
        self.password = hashlib.md5(b'some string').hexdigest()
        self.user = self.create_user('test@example.com', pk=1)
        self.setup_initconfig()

    def tearDown(self):
        super().tearDown()
        # reset authentication env to default
        _base_config.OMEGA_AUTH_ENV = prev_auth_env
        AuthenticationEnv.auth_env = None

    def create_user(self, email, username=None, pk=None):
        username = username or email
        user = User.objects.create_user(username, email,
                                        self.password)
        # let all auth know about this user
        sync_user_email_addresses(user)
        return user

    def test_runtime_explicit_auth_apikey(self):
        # set auth explicitely, test om.runtime is initialized properly
        auth = OmegaRuntimeAuthentication('foo', 'bar')
        om = Omega(auth=auth)
        om.runtime.pure_python = True
        om.runtime.celeryapp.conf.CELERY_ALWAYS_EAGER = True
        self.assertEquals(om.runtime.auth, auth)
        # use authentication env
        authEnv = AuthenticationEnv.secure()
        auth = OmegaRuntimeAuthentication(self.user.username,
                                          self.user.api_key.key,
                                          'default')
        om = authEnv.get_omega_for_task(None, auth=auth.token)
        self.assertEquals(om.runtime.auth.token, auth.token)

    def test_runtime_explicit_auth_jwt_apikey_authenv(self):
        # use apikey authentication env, however providing a jwt token
        # note this uses the special user "jwt", with apikey=jwt
        resp = self.client.post('/token-auth/',
                                content_type='application/json',
                                data={'username': self.user.email,
                                      'password': self.password})
        self.assertEqual(resp.status_code, 200)
        jwt_token = resp.json()['token']
        # we have the apikey authentication env, put pass it a JWT
        authEnv = AuthenticationEnv.secure()
        jwt_client_auth = JWTOmegaRuntimeAuthentation(jwt_token, 'default')
        # we expect the om instance to have an apikey authentication (real username, real apikey)
        om = authEnv.get_omega_for_task(None, auth=jwt_client_auth.token)
        expected_auth = OmegaRuntimeAuthentication('jwt',
                                                   jwt_token,
                                                   'default')
        self.assertEquals(om.runtime.auth.token, expected_auth.token)

    def test_runtime_explicit_auth_jwt_authenv(self):
        # use jwt authentication env, with expects and provides JWT tokens as the runtime auth
        from omegaml import _base_config
        _base_config.OMEGA_AUTH_ENV = 'omegaee.runtimes.auth.JWTCloudRuntimeAuthenticationEnv'
        # get a new token
        resp = self.client.post('/token-auth/',
                                content_type='application/json',
                                data={'username': self.user.email,
                                      'password': self.password})
        self.assertEqual(resp.status_code, 200)
        jwt_token = resp.json()['token']
        # simulate call to om runtime, using the JWT token
        AuthenticationEnv.auth_env = None
        authEnv = AuthenticationEnv.secure()
        jwt_client_auth = JWTOmegaRuntimeAuthentation(jwt_token, 'default')
        om = authEnv.get_omega_for_task(None, auth=jwt_client_auth.token)
        # we expect that we get back a jwt token, not userid/apikey
        runtime_auth = om.runtime.auth
        self.assertEquals(om.runtime.auth.token[0], 'jwt')
        self.assertNotEqual(om.runtime.auth.token[0], self.user.api_key.key)
        # check we can reuse this token to get om for another task
        om = authEnv.get_omega_for_task(None, auth=om.runtime.auth.token)
        self.assertEquals(om.runtime.auth.token, runtime_auth.token)
        # ensure userid/apikey auth is not accepted
        apikey_auth = OmegaRuntimeAuthentication(self.user.username,
                                                 self.user.api_key.key,
                                                 'default')
        with self.assertRaises(AuthenticationFailed):
            authEnv.get_omega_for_task(None, auth=apikey_auth)

    def test_runtime_implicit_auth(self):
        # set auth indirectly
        defaults = settings()
        _userid = defaults.OMEGA_USERID
        _apikey = defaults.OMEGA_APIKEY
        defaults.OMEGA_USERID = 'foo'
        defaults.OMEGA_APIKEY = 'bar'
        om = Omega()
        self.assertEquals(om.runtime.auth.userid, defaults.OMEGA_USERID)
        self.assertEquals(om.runtime.auth.apikey, defaults.OMEGA_APIKEY)
        defaults.OMEGA_USERID = _userid
        defaults.OMEGA_APIKEY = _apikey
