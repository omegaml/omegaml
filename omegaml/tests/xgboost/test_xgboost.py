import random
from unittest import TestCase

import pandas as pd
import unittest

from omegaml import Omega
from omegaml.backends.xgboost.dmatrix import XGBoostDMatrix
from omegaml.tests.util import OmegaTestMixin

import xgboost as xgb

from omegaml.util import module_available


@unittest.skipUnless(module_available("xgboost"), 'xgboost is not available')
class XGBoostTests(OmegaTestMixin, TestCase):

    def setUp(self):
        TestCase.setUp(self)
        om = self.om = Omega()
        om.datasets.register_backend(XGBoostDMatrix.KIND, XGBoostDMatrix)
        self.clean()

    def tearDown(self):
        TestCase.tearDown(self)

    def test_putget_dmatrix(self):
        om = self.om
        df = self.df = pd.DataFrame({'x': list(range(0, 20)),
                                     'y': random.sample(list(range(0, 100)), 20)})
        dm = xgb.DMatrix(df['x'], df['y'])
        meta = om.datasets.put(dm, 'dmatrix', kind=XGBoostDMatrix.KIND)
        self.assertIsInstance(meta, om.datasets._Metadata)
        self.assertEqual(meta.kind, XGBoostDMatrix.KIND)
        dm_ = om.datasets.get('dmatrix')
        self.assertIsInstance(dm_, xgb.DMatrix)


if __name__ == '__main__':
    unittest.main()
