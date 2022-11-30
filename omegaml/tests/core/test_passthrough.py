import unittest

import pandas as pd
from mongoengine import ValidationError
from omegaml import Omega
from omegaml.mixins.store.passthrough import PassthroughMixin, PassthroughDataset
from omegaml.tests.util import OmegaTestMixin
from sklearn.linear_model import LinearRegression


class PassthroughMixinTests(OmegaTestMixin, unittest.TestCase):
    def setUp(self):
        om = self.om = Omega()
        om.datasets.register_mixin(PassthroughMixin)
        self.clean()

    def test_passthrough(self):
        om = self.om
        ds = PassthroughDataset([2])
        self.assertRegex(ds, r'.system/passthrough/.*')
        # behaves like an existing dataset
        # -- data content is stored as repr(ds) in kind_meta.data
        meta = om.datasets.metadata(ds)
        self.assertIsInstance(meta, om.datasets._Metadata)
        self.assertEqual(meta.name, str(ds))
        self.assertEqual(meta.kind_meta['data'], repr(ds))
        with self.assertRaises(ValidationError):
            # there is no backend for PassthroughDataset, hence cannot be saved
            meta.save()

    def test_passthrough_runtime(self):
        om = self.om
        data = pd.DataFrame({
            'x': range(10),
            'y': range(10, 20)
        })
        reg = LinearRegression()
        reg.fit(data[['x']], data[['y']])
        om.models.put(reg, 'test')
        # explicit
        # -- check no dataset gets created by runtime
        result = om.runtime.model('test').predict(PassthroughDataset([2])).get()
        self.assertEqual(len(om.datasets.list(include_temp=True, hidden=True)), 0)
        self.assertEqual(result, [[12]])
        # implicit
        # -- check no dataset gets created by runtime
        result = om.runtime.model('test').predict([2]).get()
        self.assertEqual(len(om.datasets.list(include_temp=True, hidden=True)), 0)
        self.assertEqual(result, [[12]])


