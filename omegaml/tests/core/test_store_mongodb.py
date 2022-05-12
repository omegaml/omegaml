from __future__ import absolute_import

import os

import pandas as pd
import unittest
from mongoengine.connection import disconnect
from pandas.testing import assert_frame_equal

from omegaml.backends.rawdict import PandasRawDictBackend
from omegaml.store import OmegaStore
from omegaml.util import delete_database, json_normalize, migrate_unhashed_datasets


class StoreTests(unittest.TestCase):

    def setUp(self):
        unittest.TestCase.setUp(self)
        delete_database()
        if os.path.exists('db.sqlite'):
            os.unlink('db.sqlite')

    def tearDown(self):
        unittest.TestCase.tearDown(self)
        delete_database()
        disconnect('omega')

    def test_migrate_unhashed_name(self):
        store = OmegaStore(bucket='foo', prefix='foo/')
        df = pd.DataFrame({'x': range(100)})
        long_name = 'a' * 10
        raised = False
        error = ''
        # save as unhashed (old version)
        store.defaults.OMEGA_STORE_HASHEDNAMES = False
        meta_unhashed = store.put(df, long_name)
        # simulate upgrade, no migration
        store.defaults.OMEGA_STORE_HASHEDNAMES = True
        # check we can still retrieve
        dfx = store.get(long_name)
        assert_frame_equal(df, dfx)
        # migrate
        store.defaults.OMEGA_STORE_HASHEDNAMES = True
        migrate_unhashed_datasets(store)
        meta_migrated = store.metadata(long_name)
        # check we can still retrieve after migration
        dfx = store.get(long_name)
        assert_frame_equal(df, dfx)
        # stored hashed
        meta_hashed = store.put(df, long_name, append=False)
        # check migration worked as expected
        self.assertNotEqual(meta_unhashed.collection, meta_hashed.collection)
        self.assertEqual(meta_migrated.collection, meta_hashed.collection)

    def test_store_dataframe_as_dfgroup(self):
        data = {
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        }
        result_data = {
            'a': list(range(1, 2)),
            'b': 1,
        }
        df = pd.DataFrame(data)
        result_df = pd.DataFrame(result_data)
        store = OmegaStore()
        groupby_columns = ['b']
        meta = store.put(df, 'dfgroup', groupby=groupby_columns)
        self.assertEqual(meta.kind, 'pandas.dfgroup')
        # make sure the collection is created
        self.assertIn(
            meta.collection, store.db.list_collection_names())
        # note column order can differ due to insertion order since pandas 0.25.1
        # hence using [] to ensure same column order for both expected, result
        df2 = store.get('dfgroup', kwargs={'b': 1})
        self.assertTrue(df2.equals(result_df[df2.columns]))
        df3 = store.get('dfgroup')
        self.assertTrue(df3.equals(df[df3.columns]))
        df4 = store.get('dfgroup', kwargs={'a': 1})
        self.assertTrue(df4.equals(result_df[df4.columns]))

    def test_arbitrary_collection_new(self):
        data = {'foo': 'bar',
                'bax': 'fox'}
        store = OmegaStore()
        store.register_backend(PandasRawDictBackend.KIND, PandasRawDictBackend)
        # create the collection
        foo_coll = store.db['foo']
        foo_coll.insert_one(data)
        # store the collection as is
        store.put(foo_coll, 'myfoo').save()
        self.assertIn('myfoo', store.list())
        # test we get back _id column if raw=True
        data_df = store.get('myfoo', raw=True)
        data_raw = store.collection('myfoo').find_one()
        assert_frame_equal(json_normalize(data_raw), data_df)
        # test we get just the data column
        data_df = store.get('myfoo', raw=False)
        data_raw = store.collection('myfoo').find_one()
        del data_raw['_id']
        assert_frame_equal(json_normalize(data_raw), data_df)
        cols = ['foo', 'bax']
        assert_frame_equal(data_df[cols], json_normalize(data_raw)[cols])
