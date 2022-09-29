import os
import sys
from unittest import mock
from uuid import uuid4

from django.contrib.auth.models import User
from django.test import TestCase
from tastypie.test import ResourceTestCaseMixin

from omegaml import Omega
from omegaops import get_client_config
from omegaweb.tests.util import OmegaResourceTestMixin
from tastypiex.requesttrace import ClientRequestTracer

# ensure the client uses the server-specified mongo url
@mock.patch.dict(os.environ, {"OMEGA_MONGO_URL": ""})
class ScriptResourceTests(OmegaResourceTestMixin, ResourceTestCaseMixin, TestCase):
    fixtures = ['landingpage']

    def setUp(self):
        super(ScriptResourceTests, self).setUp()
        # self.api_client = ClientRequestTracer(self.api_client, response=False)
        # setup django user
        self.username = username = 'test'
        self.email = email = 'test@omegaml.io'
        self.password = password = 'password'
        self.user = User.objects.create_user(username, email, password)
        self.apikey = self.user.api_key.key
        # setup omega credentials
        self.setup_initconfig()
        # setup test data
        config = get_client_config(self.user)
        om = self.om = Omega(mongo_url=config.get('OMEGA_MONGO_URL'))
        for ds in om.scripts.list():
            om.scripts.drop(ds)
        self.api_client = ClientRequestTracer(self.api_client, response=False)

    def tearDown(self):
        pass

    def url(self, pk=None, action=None, query=None):
        url = '/api/v1/script/'
        if pk is not None:
            url += '{pk}/'.format(**locals())
        if action is not None:
            url += '{action}/'.format(**locals())
        if query is not None:
            url += '?{query}'.format(**locals())
        return url

    def get_credentials(self):
        return self.create_apikey(self.username, self.apikey)

    def test_script_run(self):
        basepath = os.path.join(os.path.dirname(sys.modules['omegaml'].__file__), 'example')
        pkgpath = os.path.abspath(os.path.join(basepath, 'demo', 'helloworld'))
        om = self.om
        pkg = 'pkg://{}'.format(pkgpath)
        # put script
        meta = om.scripts.put(pkg, 'helloworld')
        # run the script on the cluster
        resp = self.api_client.post(self.url('helloworld', action='run', query='text=foo'),
                                    authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertIn('runtimes', data)
        self.assertIn('result', data)
        expected = list(['hello from helloworld', {'text': 'foo', 'pure_python': False}])
        self.assertEqual(data['result'], expected)

    def test_script_run_request_id_header(self):
        basepath = os.path.join(os.path.dirname(sys.modules['omegaml'].__file__), 'example')
        pkgpath = os.path.abspath(os.path.join(basepath, 'demo', 'helloworld'))
        om = self.om
        pkg = 'pkg://{}'.format(pkgpath)
        # put script
        meta = om.scripts.put(pkg, 'helloworld')
        # run the script on the cluster
        # -- we pass a custom request id
        # -- request id is expected to show up in log
        request_id = uuid4().hex
        with self.assertLogs(logger='root', level='INFO') as log:
            # note assertLogs does its own log formatting, so no json output here
            resp = self.api_client.post(self.url('helloworld', action='run', query='text=foo'),
                                        authentication=self.get_credentials(),
                                        HTTP_X_REQUEST_ID=request_id)
            self.assertIn(request_id, ' '.join(log.output))
        # we run another request again to check the runtime resets the task id
        request_id = uuid4().hex
        with self.assertLogs(logger='root', level='INFO') as log:
            # note assertLogs does its own log formatting, so no json output here
            resp = self.api_client.post(self.url('helloworld', action='run', query='text=foo'),
                                        authentication=self.get_credentials(),
                                        HTTP_X_REQUEST_ID=request_id)
            self.assertIn(request_id, ' '.join(log.output))
        # -- we don't send the request id, it is not supposed to show up
        #    (i.e. the omega runtime is reset to generate its own request id)
        with self.assertLogs(logger='root', level='INFO') as log:
            # note assertLogs does its own log formatting, so no json output here
            resp = self.api_client.post(self.url('helloworld', action='run', query='text=foo'),
                                        authentication=self.get_credentials())
            self.assertNotIn(request_id, ' '.join(log.output))
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertIn('runtimes', data)
        self.assertIn('result', data)
        expected = list(['hello from helloworld', {'text': 'foo', 'pure_python': False}])
        self.assertEqual(data['result'], expected)

