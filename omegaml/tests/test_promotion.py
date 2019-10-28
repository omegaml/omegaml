from unittest import TestCase

from sklearn.linear_model import LinearRegression

from omegaml import Omega
from omegaml.mixins.store.promotion import PromotionMixin
from omegaml.tests.util import OmegaTestMixin


class PromotionMixinTests(OmegaTestMixin, TestCase):
    def setUp(self):
        om = self.om = Omega()
        om.datasets.register_mixin(PromotionMixin)
        om.models.register_mixin(PromotionMixin)
        self.clean()
        self.clean('prod')

    def test_dataset_promotion(self):
        om = self.om
        prod = om['prod']
        om.datasets.put(['foo'], 'foo')
        # ensure dataset is in default bucket, not in prod
        self.assertIn('foo', om.datasets.list())
        self.assertNotIn('foo', prod.datasets.list())
        # promote to prod
        om.datasets.promote('foo', prod.datasets)
        self.assertIn('foo', prod.datasets.list())

    def test_model_promotion(self):
        om = self.om
        prod = om['prod']
        reg = LinearRegression()
        om.models.put(reg, 'mymodel')
        # ensure dataset is in default bucket, not in prod
        self.assertIn('mymodel', om.models.list())
        self.assertNotIn('mymodel', prod.models.list())
        # promote to prod
        om.models.promote('mymodel', prod.models)
        self.assertIn('mymodel', prod.models.list())
