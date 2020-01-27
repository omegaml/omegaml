from unittest import TestCase

import pandas as pd
from pandas.util.testing import assert_frame_equal, assert_series_equal

from omegaml import Omega


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
        flt_df = df == 5  # this returns a multi-column mask with all rows(!)
        expected = df[flt_df.iloc[:, 0]]  # actual meaning in in MDataFrame
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

    def test_applyoperators(self):
        om = self.om
        df = self.df
        # mult
        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(lambda v: v * 5)
        expected = df * 5
        assert_frame_equal(expected, mdf.value)
        # add
        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(lambda v: v + 5)
        expected = df + 5
        assert_frame_equal(expected, mdf.value)
        # div
        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(lambda v: v / 2)
        expected = df / 2
        assert_frame_equal(expected, mdf.value)
        # truediv
        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(lambda v: v // 2)
        expected = df // 2
        assert_frame_equal(expected.astype(float), mdf.value)
        # minus
        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(lambda v: v - 2)
        expected = df - 2
        assert_frame_equal(expected, mdf.value)
        # complex
        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(lambda v: (v - 2) * 5)
        expected = (df - 2) * 5
        assert_frame_equal(expected, mdf.value)

    def test_apply_custom_project(self):
        om = self.om
        df = self.df

        def complexfn(ctx):
            ctx.add({
                '$project': {
                    'x': {
                        '$multiply': ['$x', 5]
                    },
                    'y': 1,
                }
            })
            return ctx

        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(complexfn)
        df['x'] = df['x'] * 5
        expected = df
        # note since pandas 0.25.1 column order depends on dict key
        # insertion order, using [expected.colums] is to ensure the
        # same column order -- we can't control the key order by pymongo
        assert_frame_equal(expected, mdf.value[expected.columns])

    def test_apply_custom_project_simple(self):
        om = self.om
        df = self.df

        def complexfn(ctx):
            ctx.project(x={
                '$multiply': ['$x', 5]
            }, b={'$divide': ['$x', 5]})
            return ctx

        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(complexfn)
        # simulate parallel ops
        df['x'], df['b'] = df['x'] * 5, df['x'] / 5
        value = mdf.value
        expected = df[value.columns]
        self.assertEquals(sorted(['x', 'b']), sorted(expected))
        assert_frame_equal(expected, value)

    def test_apply_dict(self):
        om = self.om

        df = pd.DataFrame({
            'x': pd.date_range(start=pd.to_datetime('09.05.2018',
                                                    format='%m.%d.%Y'), periods=5, tz=None),
            'y': range(5),
        })
        om.datasets.put(df, 'sample', append=False)

        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(lambda v: dict(a=v['x'].dt.dayofweek,
                                       b=v['x'].dt.year)).value

        self.assertEqual(list(mdf['a'].values), [4, 5, 6, 7, 1])
        self.assertTrue(all(v == 2018 for v in mdf['b'].values))

    def test_apply_dt(self):
        om = self.om

        df = pd.DataFrame({
            'x': pd.date_range(start='now', periods=5, tz=None),
            'y': range(5),
        })
        om.datasets.put(df, 'sample', append=False)

        mdf = om.datasets.getl('sample')
        # FIXME we have to convert MongoDB dayofweek to Pandas dt.dayofweek
        # they start at different days of the week with different base index
        value = mdf.apply(lambda v: ((v['x'].dt.dayofweek) + 5) % 7).value
        expected = df['x'].dt.dayofweek
        assert_series_equal(expected, value['x'])

    def test_apply_str_concat(self):
        om = self.om

        df = pd.DataFrame({
            'x': ['abc', 'def'],
            'b': ['xyz', 'nop'],
        })
        om.datasets.put(df, 'sample', append=False)

        # test on dataframe
        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(lambda v: v.str.concat(['*', 'b'])).value
        self.assertEqual(list(mdf['x'].values), ['abc*xyz', 'def*nop'])
        self.assertEqual(list(mdf['b'].values), ['xyz*xyz', 'nop*nop'])
        # test on series
        mdf = om.datasets.getl('sample')
        mdf = mdf['x'].apply(lambda v: v.str.concat(['foo'])).value
        self.assertEqual(list(mdf.values), ['abcfoo', 'deffoo'])

    def test_apply_str_split(self):
        om = self.om

        df = pd.DataFrame({
            'x': ['abc', 'def'],
            'b': ['xyz', 'nop'],
        })
        om.datasets.put(df, 'sample', append=False)

        # test on dataframe
        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(lambda v: v.str.split('a')).value
        self.assertEqual(list(mdf['x'].values), ['', 'bc', 'def'])
        self.assertEqual(list(mdf['b'].values), ['xyz', 'xyz', 'nop'])
        # test on series
        mdf = om.datasets.getl('sample')
        mdf = mdf['x'].apply(lambda v: v.str.split(['a'])).value
        self.assertEqual(mdf.name, 'x')
        self.assertEqual(list(mdf.values), ['', 'bc', 'def'])

    def test_apply_str_lower(self):
        om = self.om

        df = pd.DataFrame({
            'x': ['ABC', 'DEF'],
            'b': ['XYZ', 'NOP'],
        })
        om.datasets.put(df, 'sample', append=False)

        # test on dataframe
        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(lambda v: v.str.lower()).value
        self.assertEqual(list(mdf['x'].values), ['abc', 'def'])
        self.assertEqual(list(mdf['b'].values), ['xyz', 'nop'])
        # test on series
        mdf = om.datasets.getl('sample')
        mdf = mdf['x'].apply(lambda v: v.str.lower()).value
        self.assertEqual(list(mdf.values), ['abc', 'def'])
        self.assertEqual(mdf.name, 'x')
        mdf = om.datasets.getl('sample')
        mdf = mdf['b'].apply(lambda v: v.str.lower()).value
        self.assertEqual(list(mdf.values), ['xyz', 'nop'])
        self.assertEqual(mdf.name, 'b')

    def test_apply_str_substr(self):
        om = self.om

        df = pd.DataFrame({
            'x': ['abc', 'def'],
            'b': ['xyz', 'nop'],
        })
        om.datasets.put(df, 'sample', append=False)

        # test on dataframe
        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(lambda v: v.str.substr(0, 2)).value
        self.assertEqual(list(mdf['x'].values), ['ab', 'de'])
        self.assertEqual(list(mdf['b'].values), ['xy', 'no'])
        # test on series
        mdf = om.datasets.getl('sample')
        mdf = mdf['x'].apply(lambda v: v.str.substr(0, 2)).value
        self.assertEqual(list(mdf.values), ['ab', 'de'])
        self.assertEqual(mdf.name, 'x')
        mdf = om.datasets.getl('sample')
        mdf = mdf['b'].apply(lambda v: v.str.substr(0, 2)).value
        self.assertEqual(list(mdf.values), ['xy', 'no'])
        self.assertEqual(mdf.name, 'b')

    def test_apply_str_isequal(self):
        om = self.om

        df = pd.DataFrame({
            'x': ['abc', 'def'],
            'b': ['xyz', 'nop'],
        })
        om.datasets.put(df, 'sample', append=False)

        # test on dataframe
        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(lambda v: v.str.isequal('abc')).value
        self.assertEqual(list(mdf['x'].values), [True, False])
        self.assertEqual(list(mdf['b'].values), [False, False])
        # test on series
        mdf = om.datasets.getl('sample')
        mdf = mdf['x'].apply(lambda v: v.str.isequal('abc')).value
        self.assertEqual(list(mdf.values), [True, False])
        self.assertEqual(mdf.name, 'x')
        mdf = om.datasets.getl('sample')
        mdf = mdf['b'].apply(lambda v: v.str.isequal('abc')).value
        self.assertEqual(list(mdf.values), [False, False])
        self.assertEqual(mdf.name, 'b')

    def test_apply_str_len(self):
        om = self.om

        df = pd.DataFrame({
            'x': ['abc', 'def'],
            'b': ['xxyz', 'noppp'],
        })
        om.datasets.put(df, 'sample', append=False)

        # test on dataframe
        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(lambda v: v.str.len()).value
        self.assertEqual(list(mdf['x'].values), [3, 3])
        self.assertEqual(list(mdf['b'].values), [4, 5])
        # test on series
        mdf = om.datasets.getl('sample')
        mdf = mdf['x'].apply(lambda v: v.str.len()).value
        self.assertEqual(list(mdf.values), [3, 3])
        self.assertEqual(mdf.name, 'x')
        mdf = om.datasets.getl('sample')
        mdf = mdf['b'].apply(lambda v: v.str.len()).value
        self.assertEqual(list(mdf.values), [4, 5])
        self.assertEqual(mdf.name, 'b')

    def test_apply_str_index(self):
        om = self.om

        df = pd.DataFrame({
            'x': ['abc', 'def'],
            'b': ['xxbc', 'bcxz'],
        })
        om.datasets.put(df, 'sample', append=False)

        # test on dataframe
        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(lambda v: v.str.index('bc')).value
        self.assertEqual(list(mdf['x'].values), [1, -1])
        self.assertEqual(list(mdf['b'].values), [2, 0])
        # test on series
        mdf = om.datasets.getl('sample')
        mdf = mdf['x'].apply(lambda v: v.str.index('bc')).value
        self.assertEqual(list(mdf.values), [1, -1])
        self.assertEqual(mdf.name, 'x')
        mdf = om.datasets.getl('sample')
        mdf = mdf['b'].apply(lambda v: v.str.index('bc')).value
        self.assertEqual(list(mdf.values), [2, 0])
        self.assertEqual(mdf.name, 'b')

    def test_apply_groupby_math(self):
        om = self.om

        df = pd.DataFrame({
            'x': ['abc', 'def'] * 5,
            'v': range(7, 17),
        })

        om.datasets.put(df, 'sample', append=False)

        def groupby(ctx):
            ctx.groupby('x', v={'$sum': '$v'})['v'] * 2

        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(groupby)
        expected = df.groupby('x').agg(dict(v='sum')) * 2
        assert_frame_equal(expected, mdf.value)

    def test_apply_groupby_inline(self):
        om = self.om

        df = pd.DataFrame({
            'x': ['abc', 'def'] * 5,
            'v': range(7, 17),
        })

        om.datasets.put(df, 'sample', append=False)

        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(lambda v: v.groupby('x').sum('v'))
        expected = df.groupby('x').agg(dict(v='sum')).rename(columns=dict(v='v_sum'))
        assert_frame_equal(expected, mdf.value)

    def test_apply_groupby_agg(self):
        om = self.om

        df = pd.DataFrame({
            'x': ['abc', 'def'] * 5,
            'v': range(7, 17),
        })

        om.datasets.put(df, 'sample', append=False)

        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(lambda v: v.groupby('x').agg(v=['sum', 'mean', 'std'])).value
        expected = df.groupby('x').agg(dict(v=['sum', 'mean', 'std']))
        self.assertEqual(list(expected[('v', 'sum')].values), list(mdf['v_sum'].values))

    def test_apply_groupby_agg(self):
        om = self.om

        df = pd.DataFrame({
            'x': ['abc', 'def'] * 5,
            'v': range(7, 17),
        })
        om.datasets.put(df, 'sample', append=False)

        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(lambda v: v.groupby('x').agg(v=['sum', 'mean', 'std'])).value
        expected = df.groupby('x').agg(dict(v=['sum', 'mean', 'std']))
        self.assertEqual(list(expected[('v', 'sum')].values), list(mdf['v_sum'].values))
        self.assertEqual(list(expected[('v', 'mean')].values), list(mdf['v_avg'].values))
        self.assertEqual(list(expected[('v', 'std')].values), list(mdf['v_std'].values))

    def test_apply_cache(self):
        """
        test apply cache

        note this tests the functionality of the cache, not the performance
        """
        om = self.om

        df = pd.DataFrame({
            'x': ['abc', 'def'] * 5,
            'v': range(7, 17),
        })
        om.datasets.put(df, 'sample', append=False)

        # cache a groupby, check the cache got created
        mdf = om.datasets.getl('sample')
        cache_key = mdf.apply(lambda v: v.groupby('x').agg(v=['sum', 'mean', 'std'])).reset_cache().persist()
        cursor = mdf.apply(lambda v: v.groupby('x').agg(v=['sum', 'mean', 'std']))._get_cached_cursor()
        expected = df.groupby('x').agg(dict(v=['sum', 'mean', 'std']))
        self.assertIsNotNone(cache_key)
        self.assertIsNotNone(cursor)
        # replace the data to supersede the cache, without resetting the cache
        df = pd.DataFrame({
            'x': ['abc', 'def'] * 5,
            'v': range(17, 27),
        })
        df['v'] = df['v'] / 2
        om.datasets.put(df, 'sample', append=False)
        # evaluate the groupby, expected results are taken from cache since we did not reset the cache
        mdf = mdf.apply(lambda v: v.groupby('x').agg(v=['sum', 'mean', 'std'])).value
        self.assertEqual(list(expected[('v', 'sum')].values), list(mdf['v_sum'].values))
        self.assertEqual(list(expected[('v', 'mean')].values), list(mdf['v_avg'].values))
        self.assertEqual(list(expected[('v', 'std')].values), list(mdf['v_std'].values))
        # finally reset cache
        mdf = om.datasets.getl('sample')
        mdf = mdf.apply(lambda v: v.groupby('x').agg(v=['sum', 'mean', 'std'])).reset_cache()
        # check reset was successful
        cursor = mdf.apply(lambda v: v.groupby('x').agg(v=['sum', 'mean', 'std']))._get_cached_cursor()
        mdf = mdf.value
        self.assertIsNone(cursor)
        self.assertNotEqual(list(expected[('v', 'sum')].values), list(mdf['v_sum'].values))
        self.assertNotEqual(list(expected[('v', 'mean')].values), list(mdf['v_avg'].values))
        self.assertNotEqual(list(expected[('v', 'std')].values), list(mdf['v_std'].values))
        # try again with a full cache reset
        mdf = om.datasets.getl('sample')
        mdf.apply(lambda v: v.groupby('x').agg(v=['sum', 'mean', 'std'])).persist()
        cursor = mdf.apply(lambda v: v.groupby('x').agg(v=['sum', 'mean', 'std']))._get_cached_cursor()
        self.assertIsNotNone(cursor)
        # make sure we get a fresh mdf without any apply groups so we can test cache reset in full on collection
        mdf = om.datasets.getl('sample')
        mdf.reset_cache(full=True)
        cursor = mdf.apply(lambda v: v.groupby('x').agg(v=['sum', 'mean', 'std']))._get_cached_cursor()
        self.assertIsNone(cursor)

    def test_apply_quantile(self):
        """
        test covariance
        """
        om = self.om
        df = pd.DataFrame({
            'x': range(1000),
            'y': range(1000),
        })
        om.datasets.put(df, 'qtest', append=False)
        mdf = om.datasets.getl('qtest')
        result = mdf.quantile([.1, .2]).value
        # FIXME this is actually wrong, see df.quantile([.1, .2])
        self.assertListEqual(list(result.loc['p0.1'].values), [100, 100])
        self.assertListEqual(list(result.loc['p0.2'].values), [200, 200])

    def test_apply_covariance(self):
        """
        test covariance
        """
        om = self.om
        df = pd.DataFrame({
            'x': range(10),
            'y': range(10, 20),
        })
        om.datasets.put(df, 'covtest', append=False)
        expected = df.cov()
        mdf = om.datasets.getl('covtest')
        result = mdf.cov().value
        assert_frame_equal(result, expected)

    def test_apply_correlation(self):
        """
        test covariance
        """
        om = self.om
        df = pd.DataFrame({
            'x': range(10),
            'y': range(10, 20),
        })
        om.datasets.put(df, 'corrtest', append=False)
        expected = df.corr()
        mdf = om.datasets.getl('corrtest')
        result = mdf.corr().value
        assert_frame_equal(result, expected)
