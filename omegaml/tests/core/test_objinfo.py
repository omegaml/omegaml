from unittest import TestCase

import pandas as pd
from omegaml import Omega
from omegaml.mixins.store.objinfo import ObjectInformationMixin
from omegaml.tests.util import OmegaTestMixin
from pprint import pprint


class ObjectInformationMixinTests(OmegaTestMixin, TestCase):
    def setUp(self):
        self.om = om = Omega()
        om.datasets.register_mixin(ObjectInformationMixin)
        self.clean()

    def test_summary(self):
        om = self.om
        data = [1, 2, 3]
        om.datasets.put(data, 'test', attributes={
            'docs': 'foobar'
        })
        summary = om.datasets.summary('test')
        self.assertIsInstance(summary, dict)
        self.assertIn('docs', summary)

    def test_stats_mixin(self):
        om = self.om
        data = {'foo': 'bar'}
        om.datasets.put(data, 'test')
        stats = om.datasets.stats('test', as_dict=True)
        self.assertIn('totalSize', stats['test'])

    def test_all_store_stats(self):
        om = self.om
        data = {'foo': 'bar'}
        om.datasets.put(data, 'test')
        om.datasets.put(data, 'test2')
        om.models.put(data, 'test2')
        # get stats for all stores, in bytes
        bytes_stats = om.stats(as_dict=True)
        pprint(bytes_stats)
        self.assertIn('datasets', bytes_stats)
        self.assertIn('models', bytes_stats)
        self.assertEqual(bytes_stats['datasets']['count'], 2)
        self.assertEqual(bytes_stats['models']['count'], 1)
        # test we can get stats for each scale factor
        for scale, scalef in [('kb', 1e3), ('mb', 1e6), ('gb', 1e9), ('tb', 1e12)]:
            # by scale factor as a string
            stats = om.stats(scale=scale, as_dict=True)
            self.assertIn('datasets', stats)
            self.assertIn('models', stats)
            self.assertEqual(stats['datasets']['count'], 2)
            self.assertEqual(stats['models']['count'], 1)
            self.assertEqual(stats['datasets']['totalSize'],
                             bytes_stats['datasets']['totalSize'] // scalef)
            # by scale factor as a float
            stats = om.stats(scale=scalef, as_dict=True)
            self.assertIn('datasets', stats)
            self.assertIn('models', stats)
            self.assertEqual(stats['datasets']['count'], 2)
            self.assertEqual(stats['models']['count'], 1)
            self.assertEqual(stats['datasets']['totalSize'],
                             bytes_stats['datasets']['totalSize'] // scalef)

    def test_all_store_stats_as_df(self):
        om = self.om
        data = {'foo': 'bar'}
        om.datasets.put(data, 'test')
        om.datasets.put(data, 'test2')
        om.models.put(data, 'test2')
        # get stats for all stores, in bytes
        bytes_stats = om.stats()
        self.assertIsInstance(bytes_stats, pd.DataFrame)
        self.assertIn('datasets', bytes_stats.index)
        self.assertIn('models', bytes_stats.index)
        self.assertEqual(bytes_stats.loc['datasets']['count'], 2)
        self.assertEqual(bytes_stats.loc['models']['count'], 1)

    def test_dbstats(self):
        om = self.om
        dbstats = om.datasets.dbstats(as_dict=True)
        self.assertIsInstance(dbstats, dict)
        self.assertIn('fsAvailableSize', dbstats)
        self.assertIn('fsUsedSize', dbstats)
        self.assertIn('fsTotalSize', dbstats)
        self.assertIn('fsUsedSize%', dbstats)
        self.assertIn('fsAvailableSize%', dbstats)
