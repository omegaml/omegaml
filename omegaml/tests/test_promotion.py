from unittest import TestCase, skip

import numpy as np
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
        self.assertEqual(om.datasets.get('foo'), prod.datasets.get('foo'))

    def test_model_promotion(self):
        om = self.om
        prod = om['prod']
        reg = LinearRegression()
        om.models.put(reg, 'mymodel')
        reg_ = om.models.get('mymodel')
        self.assertIsInstance(reg_, LinearRegression)
        # ensure dataset is in default bucket, not in prod
        self.assertIn('mymodel', om.models.list())
        self.assertNotIn('mymodel', prod.models.list())
        # promote to prod
        om.models.promote('mymodel', prod.models)
        self.assertIn('mymodel', prod.models.list())

    def test_model_promotion_versioned(self):
        om = self.om
        prod = om['prod']
        reg = LinearRegression()
        om.models.put(reg, 'mymodel')
        reg_ = om.models.get('mymodel')
        self.assertIsInstance(reg_, LinearRegression)
        # ensure dataset is in default bucket, not in prod
        self.assertIn('mymodel', om.models.list())
        self.assertNotIn('mymodel', prod.models.list())
        # promote to prod
        om.models.promote('mymodel', prod.models)
        self.assertIn('mymodel', prod.models.list())
        # promote a second version
        om.models.promote('mymodel', prod.models, drop=False)
        commits = prod.models.metadata('mymodel').attributes['versions']['commits']
        self.assertEqual(len(commits), 2)

    def test_versioned_model_promotion(self):
        om = self.om
        prod = om['prod']
        reg = LinearRegression()
        om.models.put(reg, 'mymodel', tag='latest')
        reg_ = om.models.get('mymodel')
        self.assertIsInstance(reg_, LinearRegression)
        # ensure dataset is in default bucket, not in prod
        self.assertIn('mymodel', om.models.list())
        self.assertNotIn('mymodel', prod.models.list())
        # promote to prod
        om.models.promote('mymodel@latest', prod.models)
        self.assertIn('mymodel', prod.models.list())

    def test_promotion_runtime(self):
        om = self.om
        prod = om['prod']
        reg = LinearRegression()
        om.models.put(reg, 'mymodel')
        # ensure dataset is in default bucket, not in prod
        self.assertIn('mymodel', om.models.list())
        self.assertNotIn('mymodel', prod.models.list())
        # try running on default runtime
        X = np.random.randint(0, 100, (100,)).reshape(-1, 1)
        Y = X * 2
        result = om.runtime.model('mymodel').fit(X, Y).get()
        assert 'Metadata' in result
        # try running on prod runtime -- should not work
        with self.assertRaises(AssertionError):
            prod.runtime.model('mymodel').fit(X, Y).get()
        # promote to prod
        om.models.promote('mymodel', prod.models)
        # try running on prod runtime -- now should work
        result = prod.runtime.model('mymodel').fit(X, Y).get()
        assert 'Metadata' in result
        self.assertIn('mymodel', prod.models.list())

    def test_promotion_deferred(self):
        # ensure we always import injected deferred
        from omegaml import _omega
        om = _omega.OmegaDeferredInstance()
        prod = om['prod']
        reg = LinearRegression()
        om.models.put(reg, 'mymodel')
        # ensure dataset is in default bucket, not in prod
        self.assertIn('mymodel', om.models.list())
        self.assertNotIn('mymodel', prod.models.list())
        # try running on default runtime
        X = np.random.randint(0, 100, (100,)).reshape(-1, 1)
        Y = X * 2
        result = om.runtime.model('mymodel').fit(X, Y).get()
        assert 'Metadata' in result
        # try running on prod runtime -- should not work
        with self.assertRaises(AssertionError):
            prod.runtime.model('mymodel').fit(X, Y).get()
        # promote to prod
        om.models.promote('mymodel', prod.models)
        # try running on prod runtime -- now should work
        result = prod.runtime.model('mymodel').fit(X, Y).get()
        assert 'Metadata' in result
        self.assertIn('mymodel', prod.models.list())

    def test_promotion_to_self_fails(self):
        om = self.om
        reg = LinearRegression()
        om.models.put(reg, 'mymodel')
        with self.assertRaises(ValueError):
            om.models.promote('mymodel', om.models)
        om.datasets.put(['foo'], 'foo')
        with self.assertRaises(ValueError):
            om.datasets.promote('foo', om.datasets)

    def test_promotion_to_other_db_works(self):
        om = self.om
        other = Omega(mongo_url=om.mongo_url + '_promotest')
        [other.models.drop(name, force=True) for name in other.models.list(include_temp=True)]
        [other.datasets.drop(name, force=True) for name in other.datasets.list(include_temp=True)]
        reg = LinearRegression()
        reg.coef_ = 10
        # try models
        om.models.put(reg, 'mymodel')
        self.assertIn('mymodel', om.models.list())
        self.assertNotIn('mymodel', other.models.list())
        om.models.promote('mymodel', other.models)
        self.assertIn('mymodel', other.models.list())
        # ensure changes only in original
        reg.coef_ = 15
        om.models.put(reg, 'mymodel')
        self.assertNotEqual(om.models.get('mymodel').coef_, other.models.get('mymodel').coef_)
        # try datasets
        om.datasets.put(['foo'], 'foo')
        # -- ensure only in original
        self.assertIn('foo', om.datasets.list())
        self.assertNotIn('foo', other.datasets.list())
        # -- promote to other
        om.datasets.promote('foo', other.datasets)
        self.assertIn('foo', other.datasets.list())
        self.assertEqual(om.datasets.get('foo'), other.datasets.get('foo'))
        # change original ensure copy not changed
        om.datasets.put(['foo'], 'foo', append=True)
        self.assertNotEqual(om.datasets.get('foo'), other.datasets.get('foo'))
        # try models too
