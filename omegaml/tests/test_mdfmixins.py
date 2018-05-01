import random
from unittest import TestCase

from omegaml import Omega
import pandas as pd
from omegaml.store import Filter
from pandas.util.testing import assert_frame_equal, assert_series_equal


class MDataFrameMixinTests(TestCase):
    def setUp(self):
        TestCase.setUp(self)
        df = self.df = pd.DataFrame({'x': list(range(0, 10)) + list(range(0, 10)),
                                     'y': list(range(0, 10)) + list(range(0, 10))})
        om = self.om = Omega()
        om.datasets.put(df, 'sample', append=False)
        self.coll = om.datasets.collection('sample')

    def test_filterops_frame(self):
        om = self.om
        df = self.df
        mdf = om.datasets.getl('sample')
        # equality selection on frame
        flt_mdf = mdf == 5
        # note MDataFrame does not actually return a mask but applies the filter
        #      to the real data. makes more sense even though the results
        #      are somewhat different this way, but match better semantically
        flt_df = df == 5 # this returns a multi-column mask with all rows(!)
        expected = df[flt_df.iloc[:, 0]] # actual meaning in in MDataFrame
        assert_frame_equal(mdf[flt_mdf].value, expected)
        ## unequality selection
        flt_mdf = mdf < 5
        flt_df = df < 5  # this returns a multi-column mask with all rows(!)
        expected = df[flt_df.iloc[:, 0]]  # actual meaning in in MDataFrame
        assert_frame_equal(mdf[flt_mdf].value, expected)
        # combined
        flt_mdf = mdf < 5
        flt_df = df < 5  # this returns a multi-column mask with all rows(!)
        expected = df[flt_df.iloc[:, 0]]  # actual meaning in in MDataFrame
        assert_frame_equal(mdf[flt_mdf].value, expected)

    def test_filterops_series(self):
        om = self.om
        df = self.df
        mdf = om.datasets.getl('sample')
        # equality selection on frame
        flt_mdf = mdf['x'] == 5
        # note MDataFrame does not actually return a mask but applies the filter
        #      to the real data. makes more sense even though the results
        #      are somewhat different this way, but match better semantically
        flt_df = df['x'] == 5  # this returns a multi-column mask with all rows(!)
        expected = df['x'][flt_df]  # actual meaning in in MDataFrame
        assert_series_equal(mdf['x'][flt_mdf].value, expected)
        ## unequality selection
        flt_mdf = mdf < 5
        flt_df = df['x'] < 5
        expected = df['x'][flt_df]
        assert_series_equal(mdf['x'][flt_mdf].value, expected)
        # combined
        flt_mdf = mdf['x'] < 5
        flt_df = df['x'] < 5
        expected = df['x'][flt_df]  # actual meaning in in MDataFrame
        assert_series_equal(mdf['x'][flt_mdf].value, expected)
