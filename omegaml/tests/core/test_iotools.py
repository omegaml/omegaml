import os

import unittest
from pandas.util.testing import assert_frame_equal

from omegaml import Omega
import pandas as pd

from omegaml.tests.util import OmegaTestMixin


class IOToolsMixinTests(OmegaTestMixin, unittest.TestCase):
    def setUp(self):
        self.om = Omega()
        self.clean()

    def test_writecsv(self):
        om = self.om
        df = pd.DataFrame({
            'x': range(10)
        })
        om.datasets.put(df, 'testdf')
        fn = '/tmp/testdf.csv'
        os.remove(fn) if os.path.exists(fn) else None
        om.datasets.to_csv('testdf', fn, index=False)
        self.assertTrue(os.path.exists(fn))
        dfx = pd.read_csv(fn)
        assert_frame_equal(dfx, df)

    def test_writecsv_with_apply(self):
        om = self.om
        df = pd.DataFrame({
            'x': range(10)
        })
        def myfunc(df):
            df['y'] = df['x'] * 2
        om.datasets.put(df, 'testdf')
        fn = '/tmp/testdf.csv'
        os.remove(fn) if os.path.exists(fn) else None
        om.datasets.to_csv('testdf', fn, apply=myfunc)
        self.assertTrue(os.path.exists(fn))
        dfx = pd.read_csv(fn)
        self.assertIn('y', dfx.columns)

    def test_readcsv(self):
        om = self.om
        df = pd.DataFrame({
            'x': range(10)
        })
        om.datasets.put(df, 'testdf')
        fn = '/tmp/testdf.csv'
        os.remove(fn) if os.path.exists(fn) else None
        om.datasets.to_csv('testdf', fn)
        self.assertTrue(os.path.exists(fn))



