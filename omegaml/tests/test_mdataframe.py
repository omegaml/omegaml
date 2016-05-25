import os
import random
from unittest.case import TestCase

from omegaml import Omega
from omegaml.util import flatten_columns
from pandas.util.testing import assert_frame_equal

from omegaml.mdataframe import MDataFrame
import pandas as pd
class MDataFrameTests(TestCase):

    def setUp(self):
        TestCase.setUp(self)
        df = self.df = pd.DataFrame({'x': range(0, 10) + range(0, 10),
                                     'y': random.sample(range(0, 100), 20)})
        om = self.om = Omega()
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
            subdf = df[df.x == x].reset_index(drop=True)
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
            ['x', 'y'], ascending=[False, False]).reset_index(drop=True)
        self.assertTrue(df.equals(result))

    def test_mdataframe_merge(self):
        coll = self.coll
        df = self.df
        om = self.om
        other = pd.DataFrame({'x': range(0, 20),
                              'y': range(0, 20),
                              'z': range(0, 20)})
        om.datasets.put(other, 'samplez', append=False)
        coll2 = om.datasets.collection('samplez')
        result = MDataFrame(coll).merge(coll2, on='x', how='left').value
        testdf = df.merge(other, on='x', how='left')
        self.assertTrue(result.equals(testdf))

    def test_mdataframe_merge_differing_columns(self):
        coll = self.coll
        df = self.df
        om = self.om
        other = pd.DataFrame({'s': range(0, 20),
                              'y': range(0, 20),
                              'z': range(0, 20)})
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
        other = pd.DataFrame({'x': range(50, 55),
                              'y': range(0, 5),
                              'z': range(0, 5)})
        om.datasets.put(other, 'samplez', append=False)
        coll2 = om.datasets.collection('samplez')
        result = MDataFrame(coll).merge(coll2, on='x', how='left').value
        testdf = df.merge(other, on='x', how='left')
        testdf = testdf[result.columns]
        self.assertTrue(result.equals(testdf))

    def test_mdataframe_merge_partial_match(self):
        coll = self.coll
        df = self.df
        om = self.om
        other = pd.DataFrame({'x': range(0, 5),
                              'y': range(0, 5),
                              'z': range(0, 5)})
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
        other = pd.DataFrame({'x': range(0, 5),
                              'y': range(0, 5),
                              'z': range(0, 5)})
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
        other = pd.DataFrame({'x': range(0, 5),
                              'y': range(0, 5),
                              'z': range(0, 5)})
        om.datasets.put(other, 'samplez', append=False)
        coll2 = om.datasets.collection('samplez')
        result = MDataFrame(coll).merge(coll2, on='x', how='left',
                                        sort=True).value
        testdf = df.merge(other, on='x', how='left', sort=True)
        testdf = testdf[result.columns]
        self.assertTrue(result.equals(testdf))

    def test_verylarge_dataframe(self):
        if not os.environ.get('TEST_LARGE'):
            return
        other = pd.DataFrame({'x': range(0, int(10e6)),
                              'y': range(0, int(10e6)),
                              'z': range(0, int(10e6))})
        coll = self.coll
        df = self.df
        result = MDataFrame(coll).value
        self.assertEqual(set(MDataFrame(coll).columns),
                         set(list(df.columns)))
        self.assertTrue(result.equals(df))
