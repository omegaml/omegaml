from unittest import TestCase

from omegaml.backends.genai.models import GenAIBaseBackend, GenAIModel, virtual_genai, GenAIModelHandler
from omegaml.backends.genai.openai import OpenAIModelBackend, OpenAIModel
from omegaml.tests.util import OmegaTestMixin


class GenAIModelTests(OmegaTestMixin, TestCase):
    def setUp(self):
        from omegaml import Omega
        self.om = Omega()
        self.clean()
        self.om.models.register_backend(GenAIBaseBackend.KIND, GenAIBaseBackend)
        self.om.models.register_backend(OpenAIModelBackend.KIND, OpenAIModelBackend)

    def test_put_get(self):
        # create a model
        class MyModel(GenAIModelHandler):
            def complete(self, X):
                return X
        # test save and restore
        meta = self.om.models.put(MyModel, 'mymodel')
        del MyModel # ensure we can restore from scratch
        model = self.om.models.get('mymodel')
        self.assertEqual(meta.kind, GenAIBaseBackend.KIND)
        self.assertIsInstance(model, GenAIModel)
        # see if we can run complete
        X = self.om.datasets.put([1, 2, 3], 'X')
        result = model.complete(X)
        self.assertEqual(result, X)

    def test_put_get_virtualfn(self):
        @virtual_genai
        def mymodel(data=None, method=None, **kwargs):
            return data

        # test save and restore
        meta = self.om.models.put(mymodel, 'mymodel')
        del mymodel # ensure we can restore from scratch
        model = self.om.models.get('mymodel')
        self.assertEqual(meta.kind, GenAIBaseBackend.KIND)
        self.assertTrue(hasattr(model, '_omega_virtual_genai'))
        # see if we can run complete
        X = self.om.datasets.put([1, 2, 3], 'X')
        self.assertIsInstance(model, GenAIModel)
        result = model.complete(X)
        self.assertEqual(result, X)

    def test_openai(self):
        # test save and restore
        meta = self.om.models.put('openai://localhost/mymodel', 'mymodel')
        self.assertEqual(meta.kind, OpenAIModelBackend.KIND)
        self.assertEqual(meta.kind_meta['base_url'], 'https://localhost:443')
        self.assertEqual(meta.kind_meta['model'], 'mymodel')
        model = self.om.models.get('mymodel')
        self.assertIsInstance(model, OpenAIModel)
        # replace
        meta = self.om.models.put('openai://localhost;model=mymodel', 'mymodel', replace=True)
        self.assertEqual(meta.kind, OpenAIModelBackend.KIND)
        self.assertEqual(meta.kind_meta['base_url'], 'https://localhost:443')
        self.assertEqual(meta.kind_meta['model'], 'mymodel')
        # replace
        meta = self.om.models.put('openai://localhost/v1;model=mymodel', 'mymodel', replace=True)
        self.assertEqual(meta.kind, OpenAIModelBackend.KIND)
        self.assertEqual(meta.kind_meta['base_url'], 'https://localhost:443/v1')
        self.assertEqual(meta.kind_meta['model'], 'mymodel')

    def test_openai_http_scheme(self):
        # test save and restore
        meta = self.om.models.put('openai+http://localhost/mymodel', 'mymodel')
        self.assertEqual(meta.kind, OpenAIModelBackend.KIND)
        self.assertEqual(meta.kind_meta['base_url'], 'http://localhost:80')
        model = self.om.models.get('mymodel')
        self.assertIsInstance(model, OpenAIModel)
        # replace
        meta = self.om.models.put('openai+http://localhost:8080/mymodel', 'mymodel', replace=True)
        self.assertEqual(meta.kind, OpenAIModelBackend.KIND)
        self.assertEqual(meta.kind_meta['base_url'], 'http://localhost:8080')
        self.assertEqual(meta.kind_meta['model'], 'mymodel')









