from __future__ import absolute_import

import random
import string

import numpy as np
import os
import pandas as pd
import unittest
from pandas.util.testing import assert_frame_equal, assert_series_equal
from six.moves import range
from unittest.case import TestCase, skip

from omegaml import Omega
from omegaml.mdataframe import MDataFrame
from omegaml.tests.util import OmegaTestMixin
from omegaml.util import flatten_columns


class MDataFrameTests(OmegaTestMixin, TestCase):

    def setUp(self):
        TestCase.setUp(self)
        df = self.df = pd.DataFrame({'x': list(range(0, 10)) + list(range(0, 10)),
                                     'y': random.sample(list(range(0, 100)), 20)})
        om = self.om = Omega()
        self.clean()
        om.datasets.put(df, 'sample', append=False)
        self.coll = om.datasets.collection('sample')

    def tearDown(self):
        TestCase.tearDown(self)

    def test_groupby(self):
        coll = self.coll
        df = self.df
        keys = []
        for key, groupdf in MDataFrame(coll).groupby(['x']):
            x = key.get('x')
            keys.append(x)
            subdf = df[df.x == x]
            assert_frame_equal(subdf, groupdf.value)
        self.assertEqual(set(keys), set(df.x))

    def test_count(self):
        coll = self.coll
        df = self.df
        counts = MDataFrame(coll).groupby(['x']).count()
        test_counts = df.groupby('x').count()
        self.assertTrue(test_counts.equals(counts))

    def test_count_multi_columns(self):
        coll = self.coll
        df = self.df
        # add a column
        mdf = MDataFrame(coll)
        mdf['z'] = 5
        df['z'] = 5
        # group by and count
        counts = mdf.groupby(['x']).count()
        test_counts = df.groupby('x').count()
        self.assertTrue(test_counts.equals(counts))

    def test_count_column(self):
        coll = self.coll
        df = self.df
        result = MDataFrame(coll).groupby(['x']).x.count()
        testgroup = df.groupby('x').x.count()
        self.assertTrue(result.equals(testgroup))

    def test_aggregate(self):
        coll = self.coll
        df = self.df
        result = MDataFrame(coll).groupby(['x']).agg({'x': 'sum'})
        testagg = df.groupby('x').agg({'x': 'sum'})
        testagg = testagg.rename(columns=dict(x='x_sum'))
        self.assertTrue(result.equals(testagg))

    def test_aggregate_multi_stats(self):
        coll = self.coll
        df = self.df
        stats = {'x': ['sum', 'mean', 'max', 'min', 'std']}
        result = MDataFrame(coll).groupby(['x']).agg(stats)
        testagg = df.groupby('x').agg(stats)
        testagg.columns = testagg.columns.map(flatten_columns)
        testagg = testagg[result.columns]
        assert_frame_equal(testagg, result, check_dtype=False)

    def test_mdataframe(self):
        coll = self.coll
        df = self.df
        mdf = MDataFrame(coll)
        result = mdf.value
        self.assertEqual(set(MDataFrame(coll).columns),
                         set(list(df.columns)))
        self.assertTrue(result.equals(df))
        self.assertEqual(mdf.shape, df.shape)

    def test_mdataframe_count(self):
        coll = self.coll
        df = self.df
        mdf = MDataFrame(coll)
        assert_series_equal(df.count(), mdf.count())
        self.assertEqual(len(mdf), len(mdf))

    def test_mdataframe_xlarge(self):
        df = pd.DataFrame({
            'a': list(range(0, int(1e6 + 1))),
            'b': list(range(0, int(1e6 + 1)))
        })
        store = self.om.datasets
        store.put(df, 'mydata-xlarge', append=False)
        coll = store.collection('mydata-xlarge')
        result = MDataFrame(coll).value
        self.assertEqual(set(MDataFrame(coll).columns),
                         set(list(df.columns)))
        self.assertTrue(result.equals(df))

    def test_mdataframe_column_attribute(self):
        coll = self.coll
        df = self.df
        result = MDataFrame(coll).y.value
        self.assertTrue(df.y.equals(result))

    def test_mdataframe_column_slice(self):
        coll = self.coll
        df = self.df
        result = MDataFrame(coll)['y'].value
        self.assertTrue(df['y'].equals(result))

    def test_mdataframe_columns_slice(self):
        coll = self.coll
        df = self.df
        result = MDataFrame(coll)[['x', 'y']].value
        self.assertTrue(df[['x', 'y']].equals(result))

    def test_mdataframe_sort(self):
        coll = self.coll
        df = self.df
        result = MDataFrame(coll).sort(['-x', '-y']).value
        df = df.sort_values(
            ['x', 'y'], ascending=[False, False])
        assert_frame_equal(df, result)

    def test_mdataframe_merge(self):
        coll = self.coll
        df = self.df
        om = self.om
        other = pd.DataFrame({'x': list(range(0, 20)),
                              'y': list(range(0, 20)),
                              'z': list(range(0, 20))})
        om.datasets.put(other, 'samplez', append=False)
        coll2 = om.datasets.collection('samplez')
        result = MDataFrame(coll).merge(coll2, on='x', how='left').value
        testdf = df.merge(other, on='x', how='left')
        self.assertTrue(result.equals(testdf))

    def test_mdataframe_merge_differing_columns(self):
        coll = self.coll
        df = self.df
        om = self.om
        other = pd.DataFrame({'s': list(range(0, 20)),
                              'y': list(range(0, 20)),
                              'z': list(range(0, 20))})
        om.datasets.put(other, 'samplez', append=False)
        coll2 = om.datasets.collection('samplez')
        result = MDataFrame(coll).merge(coll2, left_on='x',
                                        right_on='s', how='left').value
        testdf = df.merge(other, left_on='x', right_on='s', how='left')
        testdf = testdf[result.columns]
        self.assertTrue(result.equals(testdf))

    def test_mdataframe_merge_nomatch(self):
        coll = self.coll
        df = self.df
        om = self.om
        other = pd.DataFrame({'x': list(range(50, 55)),
                              'y': list(range(0, 5)),
                              'z': list(range(0, 5))})
        om.datasets.put(other, 'samplez', append=False)
        coll2 = om.datasets.collection('samplez')
        result = MDataFrame(coll).merge(coll2, on='x', how='left').value
        testdf = df.merge(other, on='x', how='left')
        testdf = testdf[result.columns]
        self.assertTrue(result.equals(testdf))

    @unittest.skip("disalbed because MDataFrame.append fails and is very slow")
    def test_mdataframe_merge_append(self):
        ## FIXME this does not work
        coll = self.coll
        df = self.df
        om = self.om
        other = pd.DataFrame({'x': list(range(0, 5)),
                              'y': list(range(0, 5)),
                              'z': list(range(0, 5))})
        om.datasets.put(other, 'samplez', append=False)
        mdf = om.datasets.getl('samplez')
        mdf.append(mdf)
        coll2 = om.datasets.collection('samplez')
        result = MDataFrame(coll).merge(coll2, on='x', how='left', suffixes=('', '')).value
        testdf = df.append(other, ignore_index=True)
        testdf = testdf[result.columns]
        assert_frame_equal(result, testdf)

    def test_mdataframe_merge_partial_match(self):
        coll = self.coll
        df = self.df
        om = self.om
        other = pd.DataFrame({'x': list(range(0, 5)),
                              'y': list(range(0, 5)),
                              'z': list(range(0, 5))})
        om.datasets.put(other, 'samplez', append=False)
        coll2 = om.datasets.collection('samplez')
        result = MDataFrame(coll).merge(coll2, on='x', how='left').value
        testdf = df.merge(other, on='x', how='left')
        testdf = testdf[result.columns]
        self.assertTrue(result.equals(testdf))

    def test_mdataframe_merge_inner(self):
        coll = self.coll
        df = self.df
        om = self.om
        other = pd.DataFrame({'x': list(range(0, 5)),
                              'y': list(range(0, 5)),
                              'z': list(range(0, 5))})
        om.datasets.put(other, 'samplez', append=False)
        coll2 = om.datasets.collection('samplez')
        result = MDataFrame(coll).merge(coll2, on='x', how='inner',
                                        sort=True).value
        testdf = df.merge(other, on='x', how='inner', sort=True)
        testdf = testdf[result.columns]
        self.assertTrue(result.equals(testdf))

    def test_mdataframe_merge_right(self):
        coll = self.coll
        df = self.df
        om = self.om
        other = pd.DataFrame({'x': list(range(0, 5)),
                              'y': list(range(0, 5)),
                              'z': list(range(0, 5))})
        om.datasets.put(other, 'samplez', append=False)
        coll2 = om.datasets.collection('samplez')
        result = MDataFrame(coll).merge(coll2, on='x', how='left',
                                        sort=True).value
        testdf = df.merge(other, on='x', how='left', sort=True)
        testdf = testdf[result.columns]
        self.assertTrue(result.equals(testdf))

    def test_mdataframe_merge_right_cartesian(self):
        coll = self.coll
        df = self.df
        om = self.om
        other = pd.DataFrame({'x': list(range(0, 5)),
                              'y': list(range(0, 5)),
                              'z': list(range(0, 5))})
        om.datasets.put(other, 'samplez', append=False)
        om.datasets.put(other, 'samplez', append=True)
        other = om.datasets.get('samplez')
        coll2 = om.datasets.collection('samplez')
        result = MDataFrame(coll).merge(coll2, on='x', how='left',
                                        sort=True).value
        testdf = df.merge(other, on='x', how='left', sort=True)
        testdf = testdf[result.columns]
        self.assertTrue(result.equals(testdf))

    def test_mdataframe_merge_filtered(self):
        coll = self.coll
        df = self.df
        om = self.om
        other = pd.DataFrame({'x': list(range(0, 5)),
                              'y': list(range(0, 5)),
                              'z': list(range(0, 5))})
        om.datasets.put(other, 'samplez', append=False)
        om.datasets.put(other, 'samplez', append=True)
        other = om.datasets.get('samplez')
        coll2 = om.datasets.collection('samplez')
        result = MDataFrame(coll).merge(coll2, on='x', how='left',
                                        sort=True, filter=dict(x__in=[1, 2])).value
        q = df['x'].isin([1, 2])
        testdf = df[q].merge(other, on='x', how='left', sort=True)
        testdf = testdf[result.columns]
        self.assertTrue(result.equals(testdf))

    def test_verylarge_dataframe(self):
        if not os.environ.get('TEST_LARGE'):
            return
        other = pd.DataFrame({'x': list(range(0, int(10e6))),
                              'y': list(range(0, int(10e6))),
                              'z': list(range(0, int(10e6)))})
        coll = self.coll
        df = self.df
        result = MDataFrame(coll).value
        self.assertEqual(set(MDataFrame(coll).columns),
                         set(list(df.columns)))
        self.assertTrue(result.equals(df))

    def test_unique_series(self):
        coll = self.coll
        df = self.df
        om = self.om
        om.datasets.put(df, 'uniques', append=False)
        coll = om.datasets.collection('uniques')
        result = MDataFrame(coll).x.unique().value
        self.assertListEqual(list(result), list(df.x.unique()))

    def test_query_null(self):
        om = self.om
        df = pd.DataFrame({'x': list(range(0, 5)),
                           'y': [1, 2, 3, None, None]})
        om.datasets.put(df, 'foox', append=False)
        result = om.datasets.get('foox', y__isnull=True, lazy=True).value
        test = df[df.isnull().any(axis=1)]
        assert_frame_equal(result, test)

    def test_query_pandas_style(self):
        om = self.om
        df = pd.DataFrame({'x': list(range(0, 5)),
                           'y': [1, 2, 3, None, None]})
        om.datasets.put(df, 'foox', append=False)
        mdf = om.datasets.getl('foox')
        # simple subset
        mdf_flt = mdf['x'] == 4
        df_flt = df['x'] == 4
        assert_frame_equal(mdf[mdf_flt].value, df[df_flt])
        # and combined
        mdf_flt = (mdf['x'] == 4) & (mdf['x'] < 5)
        df_flt = (df['x'] == 4) & (df['x'] < 5)
        assert_frame_equal(mdf[mdf_flt].value, df[df_flt])
        # or combined
        mdf_flt = (mdf['x'] < 3) | (mdf['x'] > 3)
        df_flt = (df['x'] < 3) | (df['x'] > 3)
        assert_frame_equal(mdf[mdf_flt].value, df[df_flt])
        # negative combined
        mdf_flt = (mdf['x'] < 3) | (mdf['x'] > 3)
        df_flt = (df['x'] < 3) | (df['x'] > 3)
        assert_frame_equal(mdf[~mdf_flt].value, df[~df_flt])
        # partial negative combined

    @skip
    def test_partial_negative_query(self):
        om = self.om
        df = pd.DataFrame({'x': list(range(0, 5)),
                           'y': [1, 2, 3, None, None]})
        om.datasets.put(df, 'foox', append=False)
        mdf = om.datasets.getl('foox')
        # TODO this fails and should not
        mdf_flt = (~(mdf['x'] < 3)) | (mdf['x'] > 3)
        df_flt = (~(df['x'] < 3)) | (df['x'] > 3)
        assert_frame_equal(mdf[mdf_flt].value, df[df_flt])

    def test_locindexer_numeric_index(self):
        om = self.om
        data = {
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        }
        df = pd.DataFrame(data)
        om.datasets.put(df, 'foo', append=False)
        # by label
        dfx = om.datasets.getl('foo').loc[4].value
        assert_series_equal(df.loc[4], dfx)
        # by slice
        dfx = om.datasets.getl('foo').loc[2:4].value
        assert_frame_equal(df.loc[2:4], dfx)
        # by list
        dfx = om.datasets.getl('foo').loc[[2, 4]].value
        assert_frame_equal(df.loc[[2, 4]], dfx)
        # by ndarray
        sel = np.array([1, 2])
        dfx = om.datasets.getl('foo').loc[sel, :].value
        assert_frame_equal(df.loc[sel, :], dfx, check_names=False)

    def test_locindexer_character_index(self):
        om = self.om
        data = {
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        }
        idx = string.ascii_lowercase[0:9]
        df = pd.DataFrame(data, index=(c for c in idx))
        om.datasets.put(df, 'foo', append=False)
        # by label
        dfx = om.datasets.getl('foo').loc['c'].value
        assert_series_equal(df.loc['c'], dfx)
        # by slice
        dfx = om.datasets.getl('foo').loc['c':'f'].value
        assert_frame_equal(df.loc['c':'f'], dfx)
        # by list
        dfx = om.datasets.getl('foo').loc[['c', 'f']].value
        assert_frame_equal(df.loc[['c', 'f']], dfx)

    def test_locindexer_timeseries_index(self):
        om = self.om
        # create some dataframe
        tsidx = pd.date_range(pd.datetime(2016, 1, 1), pd.datetime(2016, 4, 1))
        df = pd.DataFrame({
            'a': list(range(0, len(tsidx))),
            'b': list(range(0, len(tsidx)))
        }, index=tsidx)
        om.datasets.put(df, 'foo', append=False)
        # by label
        dfx = om.datasets.getl('foo').loc[pd.datetime(2016, 2, 3)].value
        assert_series_equal(dfx, df.loc[pd.datetime(2016, 2, 3)])
        # by slice
        start, end = pd.datetime(2016, 2, 3), pd.datetime(2016, 2, 8)
        dfx = om.datasets.getl('foo').loc[start:end].value
        assert_frame_equal(df.loc[start:end], dfx)

    def test_locindexer_multiindex(self):
        # create some dataframe
        om = self.om
        midx = pd.MultiIndex(levels=[[u'bar', u'baz', u'foo', u'qux'],
                                     [u'one', u'two']],
                             codes=[
                                 [0, 0, 1, 1, 2, 2, 3, 3],
                                 [0, 1, 0, 1, 0, 1, 0, 1]],
                             names=[u'first', u'second'])
        df = pd.DataFrame({'x': range(0, len(midx))}, index=midx)
        om.datasets.put(df, 'foomidx', append=False)
        dfx = om.datasets.getl('foomidx').loc['bar', 'one'].value
        assert_series_equal(dfx, df.loc['bar', 'one'])

    def test_locindexer_series(self):
        """ test storing a pandas series with it's own index """
        om = self.om
        series = pd.Series(range(10),
                           name='foo',
                           index=pd.date_range(pd.datetime(2016, 1, 1),
                                               pd.datetime(2016, 1, 10)))
        om.datasets.put(series, 'fooseries', append=False)
        # try data range
        daterange = slice(pd.datetime(2016, 1, 5), pd.datetime(2016, 1, 10))
        series2 = om.datasets.getl('fooseries').loc[daterange].value
        assert_series_equal(series2, series.loc[daterange])
        # try single date
        daterange = pd.datetime(2016, 1, 5)
        series2 = om.datasets.getl('fooseries').loc[daterange].value
        self.assertEqual(series2, series.loc[daterange])

    def test_ilocindexer(self):
        om = self.om
        data = {
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        }
        idx = string.ascii_lowercase[0:9]
        df = pd.DataFrame(data, index=(c for c in idx))
        om.datasets.put(df, 'foo', append=False)
        # by single location
        dfx = om.datasets.getl('foo').iloc[0].value
        assert_series_equal(df.iloc[0], dfx)
        # by slice
        dfx = om.datasets.getl('foo').iloc[0:1].value
        assert_frame_equal(df.iloc[0:1], dfx)
        # by list
        dfx = om.datasets.getl('foo').iloc[[1, 2]].value
        assert_frame_equal(df.iloc[[1, 2]], dfx)

    def test_ilocindexer_single_column(self):
        om = self.om
        data = {
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        }
        idx = string.ascii_lowercase[0:9]
        df = pd.DataFrame(data, index=(c for c in idx))
        om.datasets.put(df, 'foo', append=False)
        # by single location
        dfx = om.datasets.getl('foo').iloc[0, 1].value
        self.assertEqual(df.iloc[0, 1], dfx)
        # by slice
        # FIXME column access by iloc is not guaranteed to return in order
        dfx = om.datasets.getl('foo').iloc[0:2, 1].value
        assert_series_equal(df.iloc[0:2, 1], dfx, check_names=False)
        # by list
        dfx = om.datasets.getl('foo').iloc[[1, 2], 1].value
        assert_series_equal(df.iloc[[1, 2], 1], dfx, check_names=False)

    def test_ilocindexer_columns(self):
        om = self.om
        data = {
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        }
        idx = string.ascii_lowercase[0:9]
        df = pd.DataFrame(data, index=(c for c in idx))
        om.datasets.put(df, 'foo', append=False)
        # by single location
        dfx = om.datasets.getl('foo').iloc[0, :].value
        assert_series_equal(df.iloc[0, :], dfx)
        # by slice
        # FIXME column access by iloc is not guaranteed to return in order
        dfx = om.datasets.getl('foo').iloc[0:2, :].value
        assert_frame_equal(df.iloc[0:2, :], dfx, check_names=False)
        # by list
        dfx = om.datasets.getl('foo').iloc[[1, 2], :].value
        assert_frame_equal(df.iloc[[1, 2], :], dfx, check_names=False)
        # by ndarray
        sel = np.array([1, 2])
        dfx = om.datasets.getl('foo').iloc[sel, :].value
        assert_frame_equal(df.iloc[sel, :], dfx, check_names=False)

    def test_ilocindexer_array(self):
        om = self.om
        data = {
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        }
        idx = string.ascii_lowercase[0:9]
        df = pd.DataFrame(data, index=(c for c in idx))
        om.datasets.put(df, 'foo', append=False)
        # by ndarray with immediate loc
        sel = np.array([1, 2])
        dfx = om.datasets.getl('foo')
        dfx.immediate_loc = True
        dfx = dfx[['a']].iloc[sel]
        assert_frame_equal(df[['a']].iloc[sel], dfx, check_names=False)
        # by ndarray with delayed loc
        sel = np.array([1, 2])
        dfx = om.datasets.getl('foo')
        dfx.immediate_loc = False
        dfx = dfx[['a']].iloc[sel].value
        assert_frame_equal(df[['a']].iloc[sel], dfx, check_names=False)

    def test_iterchunks(self):
        om = self.om
        for cdf in om.datasets.getl('sample', chunksize=2):
            self.assertEqual(len(cdf), 2)

    def test_iterrows(self):
        om = self.om
        mdf = om.datasets.getl('sample')
        df = mdf.value
        for df_row, mdf_row in zip(mdf.iterrows(), df.iterrows()):
            self.assertEqual(type(df_row), type(mdf_row))
            assert_series_equal(df_row[1], mdf_row[1])

    def test_iteritems(self):
        om = self.om
        mdf = om.datasets.getl('sample')
        df = mdf.value
        for df_row, mdf_row in zip(mdf.iteritems(), df.iteritems()):
            self.assertEqual(type(df_row), type(mdf_row))
            assert_series_equal(df_row[1], mdf_row[1])

    def test_items(self):
        om = self.om
        mdf = om.datasets.getl('sample')
        df = mdf.value
        for df_row, mdf_row in zip(mdf.items(), df.items()):
            self.assertEqual(type(df_row), type(mdf_row))
            assert_series_equal(df_row[1], mdf_row[1])
