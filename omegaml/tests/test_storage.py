from contextlib import closing
import unittest

from mongoengine.connection import disconnect

import omegaml as om
from omegaml.store.djstorage import OmegaFSStorage
from omegaml.util import override_settings, delete_database
import pandas as pd
override_settings(
    OMEGA_MONGO_URL='mongodb://localhost:27017/omegatest',
    OMEGA_MONGO_COLLECTION='store'
)


class StorageTests(unittest.TestCase):

    """ test django storages """

    def setUp(self):
        unittest.TestCase.setUp(self)
        delete_database()
        self.datasets = om.datasets

    def tearDown(self):
        unittest.TestCase.tearDown(self)
        delete_database()
        disconnect('omega')

    def test_listdir(self):
        df = pd.DataFrame({'a': range(0, 10)})
        meta = self.datasets.put(df, 'foo')
        fulllist = self.datasets.list()
        storage = OmegaFSStorage()
        result = storage.listdir('/')
        self.assertListEqual(fulllist, result)
        meta = self.datasets.put(df, 'foo2')
        result = storage.listdir('/')
        self.assertListEqual(fulllist + ['foo2'], result)

    def test_exists(self):
        df = pd.DataFrame({'a': range(0, 10)})
        meta = self.datasets.put(df, 'foo')
        fulllist = self.datasets.list()
        storage = OmegaFSStorage()
        result = storage.exists('foo')
        self.assertTrue(result)
        result = storage.exists('bar')
        self.assertFalse(result)

    def test_save(self):
        # store as dataframe
        df = pd.DataFrame({'a': range(0, 10)})
        storage = OmegaFSStorage()
        name = storage.save('foo', df)
        self.assertEqual(name, 'foo')
        # store from a json source
        df = pd.DataFrame({'a': range(0, 10)})
        storage = OmegaFSStorage()
        name = storage.save('foo2', df.to_json())
        self.assertEqual(name, 'foo2')

    def test_open(self):
        # store as dataframe
        df = pd.DataFrame({'a': range(0, 10)})
        storage = OmegaFSStorage()
        name = storage.save('foo', df)
        # open & read
        with storage.open('foo') as fin:
            text = fin.read()
        self.assertEqual(df.to_json(), text)
