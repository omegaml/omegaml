from __future__ import absolute_import

from unittest import TestCase

from omegaml.client.auth import OmegaRuntimeAuthentication
from omegaml import Omega
from omegaml.util import delete_database, settings


class AuthenticatedRuntimeTests(TestCase):

    def setUp(self):
        TestCase.setUp(self)
        delete_database()

    def tearDown(self):
        TestCase.tearDown(self)

    def test_runtime_explicit_auth(self):
        # set auth explicitely
        auth = OmegaRuntimeAuthentication('foo', 'bar')
        om = Omega(auth=auth)
        om.runtime.pure_python = True
        om.runtime.celeryapp.conf.CELERY_ALWAYS_EAGER = True
        self.assertEquals(om.runtime.auth, auth)

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
