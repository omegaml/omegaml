import unittest

from omegaml import Omega
from omegaml.util import module_available


@unittest.skipUnless(module_available("transformers"), "transformers library is not installed")
class TransformersTestCase(unittest.TestCase):
    def setUp(self):
        from omegaml.backends.transformers import TransformerModelBackend
        self.om = Omega()
        self.om.models.register_backend(TransformerModelBackend.KIND, TransformerModelBackend)

    def test_pipeline_put_get_native(self):
        # save model using TransformerModelBackend
        from transformers import pipeline, Pipeline
        from omegaml.backends.transformers import TransformerModelBackend
        om = self.om
        # build pipeline
        sentiment = pipeline("sentiment-analysis", device=-1)
        result = sentiment('life is beautiful')
        self.assertTrue(result[0].get('label'), 'POSITIVE')
        # save and get back
        meta = om.models.put(sentiment, 'sentiment', kind=TransformerModelBackend.KIND)
        self.assertIsInstance(meta, om.models._Metadata)
        reloaded = om.models.get('sentiment')
        self.assertIsInstance(reloaded, Pipeline)
        result = reloaded('life is beautiful')
        self.assertTrue(result[0].get('label'), 'POSITIVE')

    def test_pipeline_put_get_mlflow(self):
        # save model using MLFlowBackend
        from transformers import pipeline
        from omegaml.backends.mlflow.models import MLFlowModelBackend
        om = self.om
        # build pipeline
        sentiment = pipeline("sentiment-analysis", device=-1)
        result = sentiment('life is beautiful')
        self.assertTrue(result[0].get('label'), 'POSITIVE')
        # save and get back
        meta = om.models.put(sentiment, 'sentiment', kind=MLFlowModelBackend.KIND)
        self.assertIsInstance(meta, om.models._Metadata)
        reloaded = om.models.get('sentiment')
        result = reloaded.predict('life is beautiful')
        self.assertTrue(result.to_dict().get('label'), 'POSITIVE')
