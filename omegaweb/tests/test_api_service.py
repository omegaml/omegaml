import os
import sys
from django.contrib.auth.models import User
from django.test import TestCase
from marshmallow import Schema, fields
from tastypie.test import ResourceTestCaseMixin

from omegaml import Omega
from omegaml.backends.virtualobj import virtualobj
from omegaops import get_client_config
from omegaweb.tests.util import OmegaResourceTestMixin
from tastypiex.requesttrace import ClientRequestTracer


class ServiceDirectResourceTests(OmegaResourceTestMixin, ResourceTestCaseMixin, TestCase):
    fixtures = ['landingpage']
    base_url = '/api/service/'

    def setUp(self):
        super().setUp()
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
        url = self.base_url
        # avoid duplicating /service/service
        pk = pk.replace('service/', '')
        if pk is not None:
            url += '{pk}/'.format(**locals())
        if action is not None:
            url += '{action}/'.format(**locals())
        if query is not None:
            url += '?{query}'.format(**locals())
        return url

    def get_credentials(self):
        return self.create_apikey(self.username, self.apikey)

    def test_service_run_script(self):
        """ a service with no specific input and output requirements """
        # essentially just a script, but run with service semantics
        basepath = os.path.join(os.path.dirname(sys.modules['omegaml'].__file__), 'example')
        pkgpath = os.path.abspath(os.path.join(basepath, 'demo', 'helloworld'))
        om = self.om
        pkg = 'pkg://{}'.format(pkgpath)
        # put script
        meta = om.scripts.put(pkg, 'helloworld')
        # run the script on the cluster
        resp = self.api_client.post(self.url('service/helloworld', query='text=foo'),
                                    data={'foo': 'bar'},
                                    authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        expected = list(['hello from helloworld', {'text': 'foo', 'pure_python': False}])
        self.assertEqual(data.get('data'), expected)

    def test_service_script_signature_valid(self):
        """ a service with defined data type """
        # essentially just a script, but run with service semantics
        basepath = os.path.join(os.path.dirname(sys.modules['omegaml'].__file__), 'example')
        pkgpath = os.path.abspath(os.path.join(basepath, 'demo', 'helloservice'))
        om = self.om
        pkg = 'pkg://{}'.format(pkgpath)
        om.scripts.put(pkg, 'helloservice')

        # specify service input and output
        class MyInputSchema(Schema):
            factor = fields.Float()

        class MyResultSchema(Schema):
            a = fields.List(fields.Float())
            b = fields.List(fields.Float())

        om.scripts.link_datatype('helloservice', X=MyInputSchema, result=MyResultSchema)
        # can we get documentation that matches the types
        resp = self.api_client.get(self.url('helloservice', action='doc', query='text=foo'),
                                   data={'factor': 5.0},
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        specs = self.deserialize(resp)
        self.assertIn('paths', specs)
        self.assertIn('/api/service/helloservice', specs['paths'])
        self.assertIn('definitions', specs)
        self.assertIn('helloservice_X', specs['definitions'])
        self.assertIn('helloservice_result', specs['definitions'])
        # run the script
        resp = self.api_client.post(self.url('helloservice', query='text=foo'),
                                    data={'factor': 5.0},
                                    authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        expected = {'b': [0.0, 5.0, 10.0, 15.0, 20.0], 'a': [0.0, 5.0, 10.0, 15.0, 20.0]}
        self.assertEqual(data, expected)

    def test_service_script_signature_invalid(self):
        """ a service with defined data type """
        # essentially just a script, but run with service semantics
        basepath = os.path.join(os.path.dirname(sys.modules['omegaml'].__file__), 'example')
        pkgpath = os.path.abspath(os.path.join(basepath, 'demo', 'helloservice'))
        om = self.om
        pkg = 'pkg://{}'.format(pkgpath)
        om.scripts.put(pkg, 'helloservice')

        # specify service input and output
        class MyInputSchema(Schema):
            factor = fields.Float()

        class MyResultSchema(Schema):
            a = fields.List(fields.Float())
            b = fields.List(fields.Float())

        om.scripts.link_datatype('helloservice', X=MyInputSchema, result=MyResultSchema)
        # can we get documentation that matches the types
        resp = self.api_client.get(self.url('service/helloservice', action='doc'),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        specs = self.deserialize(resp)
        self.assertIn('paths', specs)
        self.assertIn('/api/service/helloservice', specs['paths'])
        self.assertIn('definitions', specs)
        self.assertIn('helloservice_X', specs['definitions'])
        self.assertIn('helloservice_result', specs['definitions'])
        # run the script
        resp = self.api_client.post(self.url('service/helloservice', query='text=foo'),
                                    data={'xfactor': 5.0},
                                    authentication=self.get_credentials())
        self.assertEqual(resp.status_code, 400)
        expected = {'message': "{'script': 'service/helloservice', 'args': ({'xfactor': 5.0},), "
                               "'kwargs': {'text': 'foo', 'xfactor': 5.0, 'pure_python': False}, "
                               '\'result\': "ValidationError({\'xfactor\': [\'Unknown '
                               'field.\']})", \'runtimes\': 0.028303, \'started\': '
                               "'2022-09-04T12:59:41.180949', 'ended': "
                               "'2022-09-04T12:59:41.209252'}"}
        self.assertTrue('ValidationError' in resp.content.decode('utf8'))

    def test_service_run_virtualobj(self):
        om = self.om

        @virtualobj
        def myscript(data=None, method=None, meta=None, store=None, tracking=None, **kwargs):
            return {'data': data, 'method': method}

        om.scripts.put(myscript, 'myscript')
        # check myscript is actually deserialized by runtime
        myscript = None
        # run the script on the cluster
        resp = self.api_client.post(self.url('service/myscript', action='run', query='text=foo'),
                                    data={'foo': 'bar'},
                                    authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        expected = {'data': {'foo': 'bar'}, 'method': 'run'}
        self.assertEqual(data, expected)

    def test_service_run_async(self):
        basepath = os.path.join(os.path.dirname(sys.modules['omegaml'].__file__), 'example')
        pkgpath = os.path.abspath(os.path.join(basepath, 'demo', 'helloworld'))
        om = self.om
        pkg = 'pkg://{}'.format(pkgpath)
        # put script
        meta = om.scripts.put(pkg, 'helloworld')
        # run the script on the cluster
        resp = self.api_client.post(self.url('service/helloworld', action='run', query='text=foo'),
                                    data={},
                                    authentication=self.get_credentials(),
                                    **self._async_headers)
        resp = self._check_async(resp)
        self.assertHttpOK(resp)
        data = self.deserialize(resp)['response']
        # since the response is not valid json, the 'data' key is inserted by GenericServiceResource
        expected = list(['hello from helloworld', {'text': 'foo', 'pure_python': False}])
        self.assertEqual(data['data'], expected)


class ServiceV1ResourceTests(ServiceDirectResourceTests):
    base_url = '/api/v1/service/'
