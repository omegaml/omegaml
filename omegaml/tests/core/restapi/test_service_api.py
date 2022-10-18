from unittest import TestCase

import os
import sys
from marshmallow import fields, Schema

from omegaml import Omega, restapi
from omegaml.backends.virtualobj import virtualobj
from omegaml.client.auth import OmegaRestApiAuth
from omegaml.tests.core.restapi.util import RequestsLikeTestClient
from omegaml.tests.util import OmegaTestMixin


class ServiceDirectResourceTests(OmegaTestMixin, TestCase):
    base_url = '/api/service/'

    def setUp(self):
        app = restapi.create_app()
        self.client = RequestsLikeTestClient(app, is_json=True)
        self.om = Omega()
        self.auth = OmegaRestApiAuth('user', 'pass')
        self.clean()

    def tearDown(self):
        pass

    def url(self, pk=None, action=None, query=None):
        url = self.base_url
        # avoid duplicating /service/service
        pk = pk.replace('service/', '')
        if pk is not None:
            url += '{pk}/'.format(**locals())
        if action is not None:
            url += '{action}'.format(**locals())
        if query is not None:
            url += '?{query}'.format(**locals())
        return url

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
        resp = self.client.post(self.url('service/helloworld', query='text=foo'), json={'foo': 'bar'})
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        # note the json payload is not sent back, because it is not passed as **kwargs but as part of *args
        expected = [{'*': None}, {'text': 'foo', 'pure_python': False}]
        self.assertEqual(data, expected)

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
        resp = self.client.get(self.url('helloservice', action='doc', query='text=foo'), json={'factor': 5.0})
        self.assertHttpOK(resp)
        specs = resp.json
        self.assertIn('paths', specs)
        self.assertIn('/api/service/helloservice', specs['paths'])
        self.assertIn('definitions', specs)
        self.assertIn('helloservice_X', specs['definitions'])
        self.assertIn('helloservice_result', specs['definitions'])
        # run the script
        resp = self.client.post(self.url('helloservice', query='text=foo'), json={'factor': 5.0})
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
        resp = self.client.get(self.url('service/helloservice', action='doc'))
        self.assertHttpOK(resp)
        specs = resp.json
        self.assertIn('paths', specs)
        self.assertIn('/api/service/helloservice', specs['paths'])
        self.assertIn('definitions', specs)
        self.assertIn('helloservice_X', specs['definitions'])
        self.assertIn('helloservice_result', specs['definitions'])
        # run the script
        resp = self.client.post(self.url('service/helloservice', query='text=foo'), json={'xfactor': 5.0})
        self.assertEqual(resp.status_code, 400)
        expected = {'message': "{'script': 'service/helloservice', 'args': ({'xfactor': 5.0},), "
                               "'kwargs': {'text': 'foo', 'xfactor': 5.0, 'pure_python': False}, "
                               '\'result\': "ValidationError({\'xfactor\': [\'Unknown '
                               'field.\']})", \'runtimes\': 0.028303, \'started\': '
                               "'2022-09-04T12:59:41.180949', 'ended': "
                               "'2022-09-04T12:59:41.209252'}"}
        self.assertTrue('ValidationError' in resp.json['message'])

    def test_service_model_signature_invalid(self):
        """ a service with defined data type """
        # essentially just a script, but run with service semantics
        basepath = os.path.join(os.path.dirname(sys.modules['omegaml'].__file__), 'example')
        pkgpath = os.path.abspath(os.path.join(basepath, 'demo', 'helloservice'))
        om = self.om
        pkg = 'pkg://{}'.format(pkgpath)
        om.models.put(pkg, 'helloservice')

        # specify service input and output
        class MyInputSchema(Schema):
            factor = fields.Float()

        class MyResultSchema(Schema):
            a = fields.List(fields.Float())
            b = fields.List(fields.Float())

        om.models.link_datatype('helloservice', X=MyInputSchema, result=MyResultSchema)
        # can we get documentation that matches the types
        resp = self.client.get(self.url('service/helloservice', action='doc'))
        self.assertHttpOK(resp)
        specs = resp.json
        self.assertIn('paths', specs)
        self.assertIn('/api/service/helloservice', specs['paths'])
        self.assertIn('definitions', specs)
        self.assertIn('helloservice_X', specs['definitions'])
        self.assertIn('helloservice_result', specs['definitions'])
        # run the script
        resp = self.client.post(self.url('service/helloservice', query='text=foo'), json={'xfactor': 5.0})
        self.assertEqual(resp.status_code, 400)
        expected = {'message': "{'script': 'service/helloservice', 'args': ({'xfactor': 5.0},), "
                               "'kwargs': {'text': 'foo', 'xfactor': 5.0, 'pure_python': False}, "
                               '\'result\': "ValidationError({\'xfactor\': [\'Unknown '
                               'field.\']})", \'runtimes\': 0.028303, \'started\': '
                               "'2022-09-04T12:59:41.180949', 'ended': "
                               "'2022-09-04T12:59:41.209252'}"}
        self.assertTrue('ValidationError' in resp.json['message'])

    def test_service_run_virtualobj_script(self):
        om = self.om

        @virtualobj
        def myscript(data=None, method=None, meta=None, store=None, tracking=None, **kwargs):
            return {'data': data, 'method': method}

        om.scripts.put(myscript, 'myscript')
        # check myscript is actually deserialized by runtime
        myscript = None
        # run the script on the cluster
        resp = self.client.post(self.url('service/myscript', action='run', query='text=foo'), json={'foo': 'bar'})
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        expected = {'data': {'foo': 'bar'}, 'method': 'run'}
        self.assertEqual(data, expected)

    def test_service_predict_virtualobj_model_signature(self):
        om = self.om

        @virtualobj
        def mymodel(data=None, method=None, meta=None, store=None, tracking=None, **kwargs):
            if kwargs.get('invalid'):
                result = {'data': data, 'method': method}
            else:
                result = {'a': [1.0], 'b': [2.0]}
            return result

        # specify service input and output
        class MyInputSchema(Schema):
            factor = fields.Float()

        class MyResultSchema(Schema):
            a = fields.List(fields.Float())
            b = fields.List(fields.Float())

        om.models.put(mymodel, 'mymodel')
        om.models.link_datatype('mymodel', X=MyInputSchema, Y=MyResultSchema, actions=['predict'])
        # check mymodel is actually deserialized by runtime
        mymodel = None
        # run the script on the cluster
        # -- invalid response, expect validation error
        resp = self.client.post(self.url('service/mymodel', action='predict', query='invalid=1'),
                                json={'factor': 1.0})
        self.assertEqual(resp.status_code, 400)
        data = self.deserialize(resp)
        self.assertIn('ValidationError', str(data))
        # -- valid response, expect response data
        resp = self.client.post(self.url('service/mymodel', action='predict', query='text=foo'), json={'factor': 1.0})
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        expected = {'a': [1.0], 'b': [2.0]}
        self.assertEqual(data, expected)
        # run again with invalid signature
        resp = self.client.post(self.url('service/mymodel', action='predict', query='text=foo'), json={'xfactor': 1.0})
        self.assertEqual(resp.status_code, 400)
        self.assertTrue('ValidationError' in resp.json['message'])

    def test_service_noaction_virtualobj_model_signature(self):
        om = self.om

        @virtualobj
        def mymodel(data=None, method=None, meta=None, store=None, tracking=None, **kwargs):
            if kwargs.get('invalid'):
                result = {'data': data, 'method': method}
            else:
                result = {'a': 1, 'b': 2}
            return result

        # specify service input and output
        class MyInputSchema(Schema):
            factor = fields.Float()

        class MyResultSchema(Schema):
            a = fields.Float()
            b = fields.Float()

        om.models.put(mymodel, 'mymodel')
        om.models.link_datatype('mymodel', X=MyInputSchema, Y=MyResultSchema, actions=['predict'])
        # check mymodel is actually deserialized by runtime
        mymodel = None
        # run the model on the cluster
        # -- invalid response, expect validation error
        resp = self.client.post(self.url('service/mymodel', query='invalid=1'), json={'factor': 1.0})
        self.assertEqual(resp.status_code, 400)
        data = self.deserialize(resp)
        self.assertIn('ValidationError', str(data))
        # -- valid response, expect response data
        resp = self.client.post(self.url('service/mymodel'), json={'factor': 1.0})
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        expected = {'a': 1, 'b': 2}
        self.assertEqual(data, expected)
        # run again with invalid signature
        resp = self.client.post(self.url('service/mymodel', query='text=foo'), json={'xfactor': 1.0})
        self.assertEqual(resp.status_code, 400)
        self.assertTrue('ValidationError' in resp.json['message'])

    def test_service_noaction_virtualobj_model_signature_many_objects(self):
        om = self.om

        @virtualobj
        def mymodel(data=None, method=None, meta=None, store=None, tracking=None, **kwargs):
            if kwargs.get('invalid'):
                result = {'data': data, 'method': method}
            else:
                result = [{'a': 1, 'b': 2}]
            return result

        # specify service input and output
        class MyInputSchema(Schema):
            factor = fields.Float()

        class MyResultSchema(Schema):
            a = fields.Float()
            b = fields.Float()

        om.models.put(mymodel, 'mymodel')
        om.models.link_datatype('mymodel', X=[MyInputSchema], Y=[MyResultSchema])
        # check mymodel is actually deserialized by runtime
        mymodel = None
        # run the model on the cluster
        # -- invalid input, expect validation error
        resp = self.client.post(self.url('service/mymodel', query='invalid=1'), json={'factor': 1.0})
        self.assertEqual(resp.status_code, 400)
        data = self.deserialize(resp)
        self.assertIn('ValidationError', str(data))
        self.assertIn('invalid input', str(data))  # result is a dict, expected a list
        # -- invalid response, expect validation error
        resp = self.client.post(self.url('service/mymodel', query='invalid=1'), json=[{'factor': 1.0}])
        self.assertEqual(resp.status_code, 400)
        data = self.deserialize(resp)
        self.assertIn('ValidationError', str(data))
        self.assertIn('invalid input', str(data)) # result is a dict, expected a list
        # -- valid response, expect response data
        resp = self.client.post(self.url('service/mymodel'), json=[{'factor': 1.0}])
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        expected = [{'a': 1, 'b': 2}]
        self.assertListEqual(data, expected)
        self.assertDictEqual(data[0], expected[0])
        # run again with invalid signature
        resp = self.client.post(self.url('service/mymodel', query='text=foo'), json=[{'xfactor': 1.0}])
        self.assertEqual(resp.status_code, 400)
        self.assertTrue('ValidationError' in resp.json['message'])

    def test_service_predict_virtualobj_model_nosignature(self):
        om = self.om

        @virtualobj
        def mymodel(data=None, method=None, meta=None, store=None, tracking=None, **kwargs):
            return {'data': data, 'method': method}

        om.models.put(mymodel, 'mymodel')
        # check mymodel is actually deserialized by runtime
        mymodel = None
        # run the script on the cluster
        resp = self.client.post(self.url('service/mymodel', action='predict', query='text=foo'), json={'foo': 'bar'})
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        expected = {'data': [{'foo': 'bar'}], 'method': 'predict'}
        self.assertEqual(data, expected)

    def test_service_run_async(self):
        basepath = os.path.join(os.path.dirname(sys.modules['omegaml'].__file__), 'example')
        pkgpath = os.path.abspath(os.path.join(basepath, 'demo', 'helloworld'))
        om = self.om
        pkg = 'pkg://{}'.format(pkgpath)
        # put script
        meta = om.scripts.put(pkg, 'helloworld')
        # run the script on the cluster
        resp = self.client.post(self.url('service/helloworld', action='run', query='text=foo'),
                                headers=self._async_headers, json={})
        resp = self._check_async(resp)
        self.assertHttpOK(resp)
        data = self.deserialize(resp)['response']
        # since the response is not valid json, the 'data' key is inserted by GenericServiceResource
        expected = list(['hello from helloworld', {'text': 'foo', 'pure_python': False}])
        self.assertEqual(data, expected)


class ServiceV1ResourceTests(ServiceDirectResourceTests):
    base_url = '/api/v1/service/'
