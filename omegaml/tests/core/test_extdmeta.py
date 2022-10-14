import numpy as np
from datetime import datetime

import json

import pandas as pd
import unittest
from marshmallow import Schema, fields, ValidationError
from numpy.testing import assert_array_equal
from sklearn.linear_model import LinearRegression

from omegaml import Omega
from omegaml.backends.virtualobj import virtualobj
from omegaml.mixins.store.extdmeta import SignatureMixin, ModelSignatureMixin, ScriptSignatureMixin
from omegaml.tests.util import OmegaTestMixin


class ExtendedMetadataMixinTests(OmegaTestMixin, unittest.TestCase):
    # TODO test model versioning v.s. change of dataset metadata

    def setUp(self):
        om = self.om = Omega()
        om.datasets.register_mixin(SignatureMixin)
        om.models.register_mixin(ModelSignatureMixin)
        om.scripts.register_mixin(ScriptSignatureMixin)
        super().clean()

    def test_link_dataset(self):
        om = self.om
        df = pd.DataFrame({'x': range(10)})
        model = LinearRegression()
        metaX = om.datasets.put(df, 'testX')
        om.models.put(model, 'mymodel')
        om.models.link_dataset('mymodel', Xname='testX', data_store=om.datasets)
        meta = om.models.metadata('mymodel')
        self.assertEqual(meta.attributes['dataset']['Xname'], 'testX')
        self.assertIsInstance(meta.attributes['dataset']['Xmeta'], dict)
        self.assertIn('kind_meta', meta.attributes['dataset']['Xmeta'])

    def test_fitpredict_implicit_dataset(self):
        om = self.om
        df = pd.DataFrame({'x': range(10)})
        df['y'] = df['x'] * 5 + 1
        model = LinearRegression()
        # fit by the runtime, triggering ModelSigantureMixin._post_fit() to record dataset info
        om.datasets.put(df, 'test')
        om.models.put(model, 'mymodel')
        om.runtime.model('mymodel').fit('test[x]', 'test[y]').get()
        meta = om.models.metadata('mymodel')
        self.assertEqual(meta.attributes['dataset']['Xname'], 'test[x]')
        self.assertEqual(meta.attributes['dataset']['Yname'], 'test[y]')
        # predict using the default dataset
        yhat = om.models.get('mymodel').predict(df[['x']])
        result = om.runtime.model('mymodel').predict('*').get()
        assert_array_equal(result, yhat)
        # re-fit using the default datasets
        om.runtime.model('mymodel').fit('*', '*').get()
        meta = om.models.metadata('mymodel')
        self.assertEqual(meta.attributes['dataset']['Xname'], 'test[x]')
        self.assertEqual(meta.attributes['dataset']['Yname'], 'test[y]')

    def test_link_script_signature(self):
        om = self.om
        df = pd.DataFrame({'x': range(10)})
        om.scripts.put(myhandler, 'myhandler')

        class MyInputSchema(Schema):
            foo = fields.String()

        class MyResultSchema(Schema):
            data = fields.Dict()

        om.scripts.link_datatype('myhandler', X=MyInputSchema, result=MyResultSchema)
        resp = om.runtime.script('myhandler').run({'foo': 'bar', }).get()
        resp = json.loads(resp)
        self.assertIn('result', resp)
        self.assertEqual({"data": {'foo': 'bar'}}, resp['result'])
        with self.assertRaises(RuntimeError) as ex:
            om.runtime.script('myhandler').run({'foo': [1], }).get()
        self.assertIn("ValidationError({'foo': ['Not a valid string.']})", str(ex.exception))

    def test_link_docs(self):
        om = self.om
        model = LinearRegression()
        df = pd.DataFrame({'x': range(10)})
        om.datasets.put(df, 'test')
        model = LinearRegression()
        meta = om.models.put(model, 'mymodel')
        om.models.link_docs('mymodel', 'this is my model')
        om.datasets.link_docs('test', 'this is a dataset')
        self.assertIn('this is my model', f'{om.models.help("mymodel")}')
        self.assertIn('this is a dataset', f'{om.datasets.help("test")}')

    def test_link_datatype(self):
        class UserSchema(Schema):
            name = fields.Str()
            email = fields.Email()
            created_at = fields.DateTime()
            birthday = fields.Date()
            data = fields.List(fields.Integer)
            number = fields.Float()
            registered = fields.Bool()

        om = self.om
        model = LinearRegression()
        om.models.put(model, 'mymodel')
        om.models.link_datatype('mymodel', X=UserSchema)
        meta = om.models.metadata('mymodel')
        om.models.validate('mymodel', X={'name': 'foo'})
        with self.assertRaises(ValidationError):
            om.models.validate('mymodel', X={'birthday': 'foo'})

    def test_link_datatype_many(self):
        class UserSchema(Schema):
            name = fields.Str()
            email = fields.Email()
            created_at = fields.DateTime()
            birthday = fields.Date()
            data = fields.List(fields.Integer)
            number = fields.Float()
            registered = fields.Bool()

        om = self.om
        model = LinearRegression()
        om.models.put(model, 'mymodel')
        om.models.link_datatype('mymodel', X=[UserSchema], Y=[UserSchema])
        meta = om.models.metadata('mymodel')
        om.models.validate('mymodel', X=[{'name': 'foo'}], Y=[{'name': 'foo'}])
        with self.assertRaises(ValidationError):
            om.models.validate('mymodel', X={'birthday': 'foo'})
        with self.assertRaises(ValidationError):
            om.models.validate('mymodel', X={'name': 'foo'})
        specs = om.runtime.swagger(format='dict', as_service=True)

    def test_swagger_generator(self):
        om = self.om
        model = LinearRegression()
        om.models.put(model, 'mymodel')
        df = pd.DataFrame({'x': range(10)})
        om.datasets.put(df, 'testX')
        om.models.link_dataset('mymodel', Xname='testX', data_store=om.datasets,
                               actions=['predict', 'fit'])
        specs = om.runtime.swagger(format='dict')
        self.assertIn('paths', specs)
        self.assertIn('/api/v1/model/mymodel/predict', specs['paths'])
        self.assertIn('/api/v1/model/mymodel/fit', specs['paths'])
        self.assertIn('/api/v1/dataset/testX', specs['paths'])
        print(specs)

    def test_swagger_generator_as_service(self):
        om = self.om
        model = LinearRegression()
        om.models.put(model, 'mymodel')
        df = pd.DataFrame({'x': range(10)})
        om.datasets.put(df, 'testX')
        om.models.link_dataset('mymodel', Xname='testX', data_store=om.datasets,
                               actions=['predict', 'fit'])
        specs = om.runtime.swagger(format='dict', as_service=True)
        self.assertIn('paths', specs)
        self.assertIn('/api/service/mymodel', specs['paths'])
        self.assertIn('/api/service/mymodel', specs['paths'])
        self.assertIn('/api/service/testX', specs['paths'])

    def test_swagger_link_specs(self):
        # sample spec
        specs = {
            'info': {
                'title': 'omega-ml service', 'version': '1.0.0'},
            'swagger': '2.0',
            'paths': {
                '/api/service/mymodel': {
                    'post': {'summary': 'summary', 'description': 'no description',
                             'operationId': 'mymodel#predict#post',
                             'consumes': ['application/json'], 'produces': ['application/json'],
                             'parameters': [
                                 {'in': 'body', 'name': 'body', 'description': 'no description',
                                  'schema': {'$ref': '#/definitions/mymodel_X'}}],
                             'responses': {
                                 '200': {'description': 'no description',
                                         'schema': {'$ref': '#/definitions/GeneratedSchema'}}}}},
            },
            'definitions': {
                'mymodel_X': {
                    'type': 'object', 'properties': {'x': {'type': 'integer'}}},
                'GeneratedSchema': {'type': 'object', 'properties': {'data': {}}},
                'testX': {
                    'type': 'object', 'properties': {'x': {'type': 'integer'}}},
                'DatasetInput_testX': {
                    'type': 'object', 'properties': {
                        'data': {'type': 'array', 'items': {'$ref': '#/definitions/testX'}}, 'dtypes': {},
                        'append': {'type': 'boolean'}}}}}
        om = self.om
        # create a model
        model = LinearRegression()
        om.models.put(model, 'mymodel')
        # link spec to a model
        metas = om.models.link_swagger(specs)
        self.assertEqual(len(metas), 1)
        self.assertEqual(metas[0].name, 'mymodel')
        # reverse check, we expect to have a valid spec
        specs = om.runtime.swagger(format='dict', as_service=True)
        self.assertIn('paths', specs)
        self.assertIn('/api/service/mymodel', specs['paths'])
        self.assertIn('/api/service/mymodel', specs['paths'])

    def test_swagger_link_multiobjects(self):
        # sample spec
        specs = {'paths': {'/api/service/mymodel': {
            'post': {'summary': 'summary', 'description': 'no description', 'operationId': 'mymodel#predict#post',
                     'consumes': ['application/json'], 'produces': ['application/json'], 'parameters': [
                    {'in': 'body', 'name': 'body', 'description': 'no description',
                     'schema': {'$ref': '#/definitions/mymodel_X'}}],
                     'responses': {'200': {'description': 'no description',
                                           'schema': {'type': 'array',
                                                      'items': {
                                                          '$ref': '#/definitions/mymodel_Y'}}}}}}},
            'info': {'title': 'omega-ml service', 'version': '1.0.0'}, 'swagger': '2.0', 'definitions': {
                'mymodel_X': {'type': 'object',
                              'properties': {'registered': {'type': 'boolean'}, 'number': {'type': 'number'},
                                             'data': {'type': 'array', 'items': {'type': 'integer'}},
                                             'created_at': {'type': 'string', 'format': 'date-time'},
                                             'name': {'type': 'string'},
                                             'birthday': {'type': 'string', 'format': 'date'},
                                             'email': {'type': 'string'}}},
                'mymodel_Y': {'type': 'object', 'properties': {
                    'registered': {'type': 'boolean'},
                    'number': {'type': 'number'},
                    'data': {'type': 'array', 'items': {'type': 'integer'}},
                    'created_at': {'type': 'string', 'format': 'date-time'},
                    'name': {'type': 'string'},
                    'birthday': {'type': 'string', 'format': 'date'},
                    'email': {'type': 'string'}}}}}

        om = self.om
        # create a model
        model = LinearRegression()
        om.models.put(model, 'mymodel')
        # link spec to a model
        metas = om.models.link_swagger(specs)
        self.assertEqual(len(metas), 1)
        self.assertEqual(metas[0].name, 'mymodel')
        # reverse check, we expect to have a valid spec
        specs = om.runtime.swagger(format='dict', as_service=True)
        self.assertIn('paths', specs)
        self.assertIn('/api/service/mymodel', specs['paths'])
        self.assertIn('/api/service/mymodel', specs['paths'])
        print(specs)

    def test_meta_to_schema(self):
        om = self.om
        df = pd.DataFrame({'v_int': [0],
                           'v_int32': [np.int32(0)],
                           'v_int64': [np.int64(0)],
                           'v_float': [0.25],
                           'v_float32': [np.float32(0.25)],
                           'v_float64': [np.float64(0.25)],
                           'v_obj': [list()],
                           'v_datetime': [datetime.now()],
                           # not currently supported by OmegaStore
                           # 'v_timedelta': [datetime.now() - datetime.now()],
                           # 'v_date': [datetime.now().date()],
                           'v_string': ['foo']})
        meta = om.datasets.put(df, 'test')
        extdmeta = SignatureMixin()
        Schema = extdmeta._datatype_from_metadata(meta.to_dict())
        sfields = Schema().fields
        self.assertIsInstance(sfields['v_int'], fields.Integer)
        self.assertIsInstance(sfields['v_int32'], fields.Integer)
        self.assertIsInstance(sfields['v_int64'], fields.Integer)
        self.assertIsInstance(sfields['v_float'], fields.Float)
        self.assertIsInstance(sfields['v_float32'], fields.Float)
        self.assertIsInstance(sfields['v_float64'], fields.Float)
        self.assertIsInstance(sfields['v_obj'], fields.String)
        self.assertIsInstance(sfields['v_string'], fields.String)


@virtualobj
def myhandler(*args, **kwargs):
    return {'data': kwargs.get('data')}


if __name__ == '__main__':
    unittest.main()
