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

# TODO: script output and model input/output are standardized. should we allow overrides?
#       e.g. model input/output to virtualobj could be anything really (like script)
#            script output could be anything (i.e. no standard header with runtimes etc.)
#       should we
#       -- have a "bare" option, e.g. set in signatures?
#       -- have a /api/v1/raw|functional|semantic/ that essentialls links to some object and requires a signature,
#          accepts only data formatted according to signature and output?
#       -- for each api have a ?bare=1 option, or set in the header, or ??

class ExtendedMetadataMixinTests(OmegaTestMixin, unittest.TestCase):
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
        yhat = om.models.get('mymodel').predict(df[['x']])
        # predict using the default dataset
        result = om.runtime.model('mymodel').predict('*').get()
        assert_array_equal(result, yhat)
        self.assertEqual(meta.attributes['dataset']['Xname'], 'test[x]')
        self.assertEqual(meta.attributes['dataset']['Yname'], 'test[y]')
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
            om.runtime.script('myhandler').run({'foo': [1],}).get()
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

    def test_swagger_generator(self):
        om = self.om
        model = LinearRegression()
        om.models.put(model, 'mymodel')
        df = pd.DataFrame({'x': range(10)})
        om.datasets.put(df, 'testX')
        om.models.link_dataset('mymodel', Xname='testX', data_store=om.datasets)
        specs = om.runtime.swagger(format='dict')
        print(specs)
        self.assertIn('paths', specs)
        self.assertIn('/api/v1/model/mymodel/predict', specs['paths'])
        self.assertIn('/api/v1/model/mymodel/fit', specs['paths'])
        self.assertIn('/api/v1/dataset/testX/', specs['paths'])


@virtualobj
def myhandler(*args, **kwargs):
    return {'data': kwargs.get('data')}

if __name__ == '__main__':
    unittest.main()

