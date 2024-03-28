from __future__ import absolute_import

import json

import hashlib
from unittest.mock import patch

from allauth.account.utils import sync_user_email_addresses
from django.contrib.auth.models import User
from django.test import TestCase

from config.logutil import HostnameInjectingFilter
from omegaml import Omega
from omegaml import _base_config
from omegaml.client.auth import OmegaRuntimeAuthentication, AuthenticationEnv
from omegaml.util import delete_database, settings
from tastypie.authentication import ApiKeyAuthentication, MultiAuthentication

from omegaee.auth.jwtauth import OmegaJWTAuthentication
from omegaee.runtimes.auth import JWTOmegaRuntimeAuthentation
from omegaee.runtimes.auth.jwtauth import AuthenticationFailed
from omegaweb.resources.clientconfig import ClientConfigResource
from omegaweb.tests.util import OmegaResourceTestMixin
from tastypiex.centralize import ApiCentralizer

prev_config = {
    k: getattr(_base_config, k, None) for k in dir(_base_config) if k.isupper()
}


class AuthenticatedRuntimeTests(OmegaResourceTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        delete_database()
        self.password = hashlib.md5(b'some string').hexdigest()
        self.user = self.create_user('test@example.com', pk=1)
        self.setup_initconfig()
        self.override_resource_auth()

    def override_resource_auth(self):
        # demonstrates overriding resources authentication
        # Rationale: standard omegaee accepts ApiKeyAuth/SessionAuth only
        # if you need JWT, be sure to configure it explicitly to avoid
        # accidental acceptance of valid JWT of unknown source
        class JWTAuthenticatedMeta:
            authentication = MultiAuthentication(OmegaJWTAuthentication(),
                                                 ApiKeyAuthentication())

        api = ApiCentralizer()
        api.centralize_resource(ClientConfigResource, meta=JWTAuthenticatedMeta)
        # could also use:
        # from omegaweb.api import v1_api
        # api = ApiCentralizer(apis=[v1_api])
        # api.centralize(api.apis, meta=JWTAuthenticatedMeta)

    def tearDown(self):
        super().tearDown()
        # reset config and authentication env to default
        for k, v in prev_config.items():
            setattr(_base_config, k, v)
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
        # client uses apikey authentication env, however providing a jwt token
        # note this uses the special user "jwt", with apikey=jwt
        resp = self.client.post('/token-auth/',
                                content_type='application/json',
                                data={'username': self.user.email,
                                      'password': self.password})
        self.assertEqual(resp.status_code, 200)
        jwt_token = resp.json()['token']
        # we have the apikey authentication env, put pass it a JWT
        authEnv = AuthenticationEnv.secure()
        jwt_client_auth = JWTOmegaRuntimeAuthentation(f'jwt:{self.user.username}',
                                                      jwt_token, 'default')
        # we expect the om instance to have an apikey authentication (real username, real apikey)
        om = authEnv.get_omega_for_task(None, auth=jwt_client_auth.token)
        expected_auth = OmegaRuntimeAuthentication(f'jwt:{self.user.username}',
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
        jwt_client_auth = JWTOmegaRuntimeAuthentation(self.user.username,
                                                      jwt_token, 'default')
        om = authEnv.get_omega_for_task(None, auth=jwt_client_auth.token)
        # we expect that we get back a jwt token, not userid/apikey
        runtime_auth = om.runtime.auth
        self.assertEquals(om.runtime.auth.token[0], self.user.username)
        self.assertNotEqual(om.runtime.auth.token[0], self.user.api_key.key)
        # check we can reuse this token to get om for another task
        om = authEnv.get_omega_for_task(None, auth=om.runtime.auth.token)
        self.assertEquals(om.runtime.auth.token, runtime_auth.token)
        # ensure userid/apikey fallback works by default
        apikey_auth = OmegaRuntimeAuthentication(self.user.username,
                                                 self.user.api_key.key,
                                                 'default')
        self.assertEqual(apikey_auth.userid, self.user.username)
        self.assertEqual(apikey_auth.apikey, self.user.api_key.key)
        om = authEnv.get_omega_for_task(None, auth=apikey_auth)
        self.assertEquals(om.runtime.auth.token[0], self.user.username)
        self.assertEquals(om.runtime.auth.token[1], self.user.api_key.key)
        # ensure userid/apikey auth is not accepted (if switched off)
        authEnv.allow_apikey = False
        apikey_auth = OmegaRuntimeAuthentication(self.user.username,
                                                 self.user.api_key.key,
                                                 'default')
        with self.assertRaises(AuthenticationFailed):
            authEnv.get_omega_for_task(None, auth=apikey_auth)
        # ensure userid/apikey auth works if turned on
        authEnv.allow_apikey = True
        apikey_auth = OmegaRuntimeAuthentication(self.user.username,
                                                 self.user.api_key.key,
                                                 'default')
        self.assertEqual(apikey_auth.userid, self.user.username)
        self.assertEqual(apikey_auth.apikey, self.user.api_key.key)
        om = authEnv.get_omega_for_task(None, auth=apikey_auth)
        self.assertEquals(om.runtime.auth.token[0], self.user.username)
        self.assertEquals(om.runtime.auth.token[1], self.user.api_key.key)

    def test_runtime_jwt_auth_uris(self):
        # TESTFIX #377
        from omegaee.runtimes.auth.jwtauth import key_resolver
        # use jwt authentication env, with expects and provides JWT tokens as the runtime auth
        _base_config.OMEGA_AUTH_ENV = 'omegaee.runtimes.auth.JWTCloudRuntimeAuthenticationEnv'
        _base_config.JWT_PUBLIC_KEY_URI = 'http://foobar.com'
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
        # simulate fetching public keys
        # -- we don't actually fetch keys but check that the
        #    corresponding methods are called
        # -- decoding is done by jwt_decode_handler_single
        #    which we test in test_runtime_explicit_auth_jwt_authenv
        # -- thus if jwt_decode_handler_single is called we can be
        #    sure to avoid issue #377
        uri_handler = patch.object(authEnv, 'jwt_decode_from_uri')
        key_resolver = patch.object(key_resolver, 'get_public_key')
        single_decoder = patch.object(authEnv, 'jwt_decode_handler_single')
        with uri_handler as uri_handler:
            authEnv.get_payload_from_token(jwt_token, defaults=_base_config)
            uri_handler.assert_called()
        with key_resolver as key_resolver, single_decoder as single_decoder:
            key_resolver.return_value = 'public key'
            authEnv.get_payload_from_token(jwt_token, defaults=_base_config)
            key_resolver.assert_called()
            single_decoder.assert_called()

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

    def test_runtime_logging(self):
        # set auth explicitely, test om.runtime is initialized properly
        import logging
        from mock import patch
        # this interferes with test_api_scripts.test_script_run_request_id_header
        # -- reason not clear
        # -- somehow this renders celery, celery.task loggers to be disabled
        #    using a NullHandler
        # -- removing this line makes all tests pass
        # -- left here for reference in case of future issues
        # self._setup_celery_logging()
        auth = OmegaRuntimeAuthentication(self.user.username,
                                          self.user.api_key.key)
        om = Omega(auth=auth)
        om.runtime.pure_python = True
        om.runtime.celeryapp.conf.CELERY_ALWAYS_EAGER = True
        # simulate formatting
        # -- self.assertLogs() failed to capture the log records for some reason
        # -- we patch the celery.task handler to capture log records
        # -- then format each log record by the logger handler
        logger = logging.getLogger('celery.task')
        handler = logger.handlers[0]
        self.assertIsInstance(handler.filters[0], HostnameInjectingFilter)
        with patch.object(handler, 'emit') as hdx:
            # cause log messages to be issued by celery
            om.runtime.require(logging='info').ping()
            # check
            # -- each message is a json record
            # -- each message contains the requestId set to the task_id
            # -- this corresponds to the logging.yaml mapping setting
            #    mapping:
            #       requestId: task_id
            for record in hdx.call_args_list:
                msg = handler.format(*record.args)
                msg = json.loads(msg)
                self.assertIsInstance(msg, dict)
                self.assertEqual(msg['requestId'], msg['task_id'])

    def _setup_celery_logging(self):
        from celery.app.log import Logging
        from omegaml.celeryapp import app
        # disabled
        # simulate celery worker logging setup
        # -- this will trigger celery setup_logging signal
        # -- which will call omegaee.tasks.config_loggers to attach json logging formatters
        Logging(app).setup(redirect_stdouts=True)



