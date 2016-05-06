import StringIO
import unittest
from zipfile import ZipFile

from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression

from omegaml.store import OmegaStore
from omegaml.util import override_settings, delete_database
import pandas as pd
import gridfs
override_settings(
    OMEGA_MONGO_URL='mongodb://localhost:27017/omegatest',
    OMEGA_MONGO_COLLECTION='store'
)


class StoreTests(unittest.TestCase):

    def setUp(self):
        unittest.TestCase.setUp(self)
        delete_database()

    def tearDown(self):
        unittest.TestCase.tearDown(self)

    def test_package_model(self):
        # create a test model
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression()
        lr.fit(X, Y)
        result = lr.predict(X)
        # package locally
        store = OmegaStore()
        zipfname = store._package_model(lr, 'models/foo')
        # load it, try predicting
        lr2 = store._extract_model(zipfname)
        self.assertIsInstance(lr2, LogisticRegression)
        result2 = lr2.predict(X)
        self.assertTrue((result == result2).all())

    def test_put_model(self):
        # create a test model
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression()
        lr.fit(X, Y)
        result = lr.predict(X)
        # store it remote
        store = OmegaStore()
        store.put(lr, 'models/foo')
        # get it back, try predicting
        lr2 = store.get('models/foo')
        self.assertIsInstance(lr2, LogisticRegression)
        result2 = lr2.predict(X)
        self.assertTrue((result == result2).all())

    def test_put_model_with_prefix(self):
        # create a test model
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression()
        lr.fit(X, Y)
        result = lr.predict(X)
        # store it remote
        store = OmegaStore(prefix='models/')
        store.put(lr, 'foo')
        # get it back, try predicting
        lr2 = store.get('foo')
        self.assertIsInstance(lr2, LogisticRegression)
        result2 = lr2.predict(X)
        self.assertTrue((result == result2).all())

    def test_put_dataframe(self):
        # create some dataframe
        df = pd.DataFrame({
            'a': range(1, 10),
            'b': range(1, 10)
        })
        store = OmegaStore(prefix='')
        store.put(df, 'mydata')
        df2 = store.get('mydata')
        self.assertTrue(df.equals(df2), "expected dataframes to be equal")

    def test_put_python_dict(self):
        # create some data
        data = {
            'a': range(1, 10),
            'b': range(1, 10)
        }
        store = OmegaStore(prefix='')
        store.put(data, 'mydata')
        data2 = store.get('mydata')
        self.assertEquals([data], data2)

    def test_get_forced_python(self):
        """
        this tests we can retrieve data as python values

        the purpose is to test the basic mode of OmegaStore in 
        case pandas and scikit learn are not available 
        """
        store = OmegaStore(prefix='')
        # pure data
        data = {
            'a': range(1, 10),
            'b': range(1, 10)
        }
        meta = store.put(data, 'data')
        data2 = store.get('data', force_python=True)
        self.assertEqual(data, data2)
        # dataframe
        # create some dataframe
        df = pd.DataFrame({
            'a': range(1, 10),
            'b': range(1, 10)
        })
        store.put(df, 'mydata')
        df2 = store.get('mydata', force_python=True)
        for r in df2:
            del r['_id']
        df2 = pd.DataFrame(df2)
        self.assertTrue(df.equals(df2), "expected dataframes to be equal")
        # model
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression()
        lr.fit(X, Y)
        # store it remote
        store.put(lr, 'foo')
        # get it back as a zipfile
        lr2file = store.get('foo', force_python=True)
        with ZipFile(StringIO.StringIO(lr2file.read())) as zipf:
            self.assertIn('foo', zipf.namelist())

    def test_store_with_metadata(self):
        om = OmegaStore(prefix='')
        # dict
        data = {
            'a': range(1, 10),
            'b': range(1, 10)
        }
        attributes = {'foo': 'bar'}
        meta = om.put(data, 'data', attributes=attributes)
        self.assertEqual(meta.kind, 'python.data')
        self.assertEqual(meta.attributes, attributes)
        data2 = om.get('data')
        self.assertEqual([data], data2)
        # dataframe
        df = pd.DataFrame(data)
        meta = om.put(df, 'datadf', attributes=attributes)
        self.assertEqual(meta.kind, 'pandas.dfrows')
        self.assertEqual(meta.attributes, attributes)
        df2 = om.get('datadf')
        self.assertTrue(df.equals(df2), "dataframes differ")
        # model
        lr = LogisticRegression()
        meta = om.put(lr, 'mymodel', attributes=attributes)
        self.assertEqual(meta.kind, 'sklearn.joblib')
        self.assertEqual(meta.attributes, attributes)
        lr2 = om.get('mymodel')
        self.assertIsInstance(lr2, LogisticRegression)

    def test_store_dataframe_as_dfgroup(self):
        data = {
            'a': range(1, 10),
            'b': range(1, 10)
        }
        result_data = {
            'a': range(1, 2),
            'b': 1,
        }
        df = pd.DataFrame(data)
        result_df = pd.DataFrame(result_data)
        store = OmegaStore()
        groupby_columns = ['b']
        meta = store.put(df, 'dfgroup', groupby=groupby_columns)
        self.assertEqual(meta.kind, 'pandas.dfgroup')
        # make sure the collection is created
        self.assertIn('store.dfgroup.data', store.mongodb.collection_names())
        df2 = store.get('dfgroup', kwargs={'b': 1})
        self.assertTrue(df2.equals(result_df))
        df3 = store.get('dfgroup')
        self.assertTrue(df3.equals(df))
        df4 = store.get('dfgroup', kwargs={'a': 1})
        self.assertTrue(df4.equals(result_df))

    def test_store_dataframe_as_hdf(self):
        data = {
            'a': range(1, 10),
            'b': range(1, 10)
        }
        df = pd.DataFrame(data)
        store = OmegaStore()
        meta = store.put(df, 'foo', as_hdf=True)
        self.assertEqual(meta.kind, 'pandas.hdf')
        # make sure the hdf file is actually there
        self.assertIn('store.foo.hdf', store.fs.list())
        df2 = store.get('foo')
        self.assertTrue(df.equals(df2), "dataframes differ")
        override_settings(
            OMEGA_MONGO_COLLECTION='tempabcdef'
        )
        store2 = OmegaStore()
        # test hdf file is not there
        self.assertNotIn('hdfdf.hdf', store2.fs.list())
        # test a get on that bucket raises exception
        self.assertRaises(gridfs.errors.NoFile, store2.get, 'hdfdf')

    def test_drop(self):
        data = {
            'a': range(1, 10),
            'b': range(1, 10)
        }
        df = pd.DataFrame(data)
        store = OmegaStore()
        meta = store.put(df, 'hdfdf', as_hdf=True)
        self.assertTrue(store.drop('hdfdf'))
        meta = store.put(df, 'datadf')
        self.assertTrue(store.drop('datadf'))
        self.assertEqual(store.list(), [], 'expected the store to be empty')
