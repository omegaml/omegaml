from unittest import TestCase

import os
import sys

from omegaml import Omega, restapi
from omegaml.backends.virtualobj import virtualobj
from omegaml.client.auth import OmegaRestApiAuth
from omegaml.tests.core.restapi.util import RequestsLikeTestClient
from omegaml.tests.util import OmegaTestMixin


class ScriptResourceTests(OmegaTestMixin, TestCase):
    def setUp(self):
        app = restapi.create_app()
        self.client = RequestsLikeTestClient(app, is_json=True)
        self.om = Omega()
        self.auth = OmegaRestApiAuth('user', 'pass')
        self.clean()

    def tearDown(self):
        pass

    def url(self, pk=None, action=None, query=None):
        url = '/api/v1/script/'
        if pk is not None:
            url += '{pk}'.format(**locals())
        if action is not None:
            url += '/{action}'.format(**locals())
        if query is not None:
            url += '?{query}'.format(**locals())
        return url

    def test_script_run(self):
        basepath = os.path.join(os.path.dirname(sys.modules['omegaml'].__file__), 'example')
        pkgpath = os.path.abspath(os.path.join(basepath, 'demo', 'helloworld'))
        om = self.om
        pkg = 'pkg://{}'.format(pkgpath)
        # put script
        meta = om.scripts.put(pkg, 'helloworld')
        # run the script on the cluster
        resp = self.client.post(self.url('helloworld', action='run', query='text=foo'), json={'foo': 'bar'})
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertIn('runtimes', data)
        self.assertIn('result', data)
        # note the json payload is not part of the response
        expected = list(['hello from helloworld', {'text': 'foo', 'pure_python': False}])
        self.assertEqual(data['result'], expected)

    def test_script_run_virtualobj(self):
        om = self.om

        @virtualobj
        def myscript(data=None, method=None, meta=None, store=None, tracking=None, **kwargs):
            return {'data': data, 'method': method}

        om.scripts.put(myscript, 'myscript')
        # check myscript is actually deserialized by runtime
        myscript = None
        # run the script on the cluster
        resp = self.client.post(self.url('myscript', action='run', query='text=foo'), json={'foo': 'bar'})
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertIn('runtimes', data)
        self.assertIn('result', data)
        expected = {'data': {'foo': 'bar'}, 'method': 'run'}
        self.assertEqual(data['result'], expected)

    def test_script_run_async(self):
        basepath = os.path.join(os.path.dirname(sys.modules['omegaml'].__file__), 'example')
        pkgpath = os.path.abspath(os.path.join(basepath, 'demo', 'helloworld'))
        om = self.om
        pkg = 'pkg://{}'.format(pkgpath)
        # put script
        meta = om.scripts.put(pkg, 'helloworld')
        # run the script on the cluster
        resp = self.client.post(self.url('helloworld', action='run', query='text=foo'),
                                headers=self._async_headers, json={})
        resp = self._check_async(resp)
        self.assertHttpOK(resp)
        data = self.deserialize(resp)['response']
        self.assertIn('runtimes', data)
        self.assertIn('result', data)
        expected = list(['hello from helloworld', {'text': 'foo', 'pure_python': False}])
        self.assertEqual(data['result'], expected)
