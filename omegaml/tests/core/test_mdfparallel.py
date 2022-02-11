from unittest import TestCase

import pandas as pd
from pandas.util.testing import assert_frame_equal, assert_series_equal

from omegaml import Omega
from omegaml.tests.util import OmegaTestMixin


class ParallelMixinTests(OmegaTestMixin, TestCase):
    def setUp(self):
        self.om = Omega()
        self.clean()

    def test_parallel_process_persist(self):
        """
        parallel processing of mdf, persisting to a dataset
        """
        om = self.om
        large = pd.DataFrame({
            'x': range(1000)
        })

        def myfunc(df):
            df['y'] = df['x'] * 2

        om.datasets.put(large, 'largedf', append=False)
        mdf = om.datasets.getl('largedf')
        mdf.transform(myfunc).persist('largedf_transformed', om.datasets)
        self.assertIn('largedf_transformed', om.datasets.list())
        dfx = om.datasets.get('largedf_transformed')
        large['y'] = large['x'] * 2
        assert_frame_equal(dfx, large)

    def test_parallel_process_direct(self):
        """
        parallel processing of mdf, persisting to a dataset
        """

        om = self.om
        large = pd.DataFrame({
            'x': range(1000)
        })

        def myfunc(df):
            df['y'] = df['x'] * 2

        om.datasets.put(large, 'largedf', append=False)
        mdf = om.datasets.getl('largedf')
        dfx = mdf.transform(myfunc).value
        large['y'] = large['x'] * 2
        assert_frame_equal(dfx, large)

    def test_parallel_worker_resolv(self):
        """
        test worker resolves mdf, func receives native df
        """
        om = self.om
        large = pd.DataFrame({
            'x': range(1000)
        })

        def myfunc(df):
            df['y'] = df['x'] * 2

        om.datasets.put(large, 'largedf', append=False)
        mdf = om.datasets.getl('largedf')
        mdf.transform(myfunc).persist('largedf_transformed', om.datasets)
        self.assertIn('largedf_transformed', om.datasets.list())
        dfx = om.datasets.get('largedf_transformed')
        large['y'] = large['x'] * 2
        assert_frame_equal(dfx, large)

    def test_parallel_func_resolve(self):
        """
        test process function resolves mdf, return df
        """
        om = self.om
        large = pd.DataFrame({
            'x': range(1000)
        })

        def myfunc(mdf):
            df = mdf.value
            df['y'] = df['x'] * 2
            return df

        om.datasets.put(large, 'largedf', append=False)
        mdf = om.datasets.getl('largedf')
        mdf.transform(myfunc, resolve='func').persist('largedf_transformed', om.datasets)
        self.assertIn('largedf_transformed', om.datasets.list())
        dfx = om.datasets.get('largedf_transformed')
        large['y'] = large['x'] * 2
        assert_frame_equal(dfx, large)

    def test_parallel_custom_chunk(self):
        """
        test process function resolves mdf, return df
        """
        om = self.om
        large = pd.DataFrame({
            'x': range(100)
        })

        def chunker(mdf, chunksize, maxobs):
            for i in range(0, len(mdf), chunksize):
                yield mdf.skip(i).head(chunksize)

        def myfunc(df):
            df['y'] = df['x'] * 2

        om.datasets.put(large, 'largedf', append=False)
        mdf = om.datasets.getl('largedf')
        mdf.transform(myfunc, chunkfn=chunker, chunksize=5, n_jobs=1).persist('largedf_transformed', om.datasets)
        self.assertIn('largedf_transformed', om.datasets.list())
        # parallel insert may result in different row order, get back in sort order
        dfx = om.datasets.getl('largedf_transformed').sort('x').value
        large['y'] = large['x'] * 2
        self.assertEqual(len(dfx), len(large))
        assert_frame_equal(dfx.reset_index(), large.reset_index())

