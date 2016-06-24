import StringIO
from datetime import timedelta
import unittest
from zipfile import ZipFile
from mongoengine.connection import disconnect
from mongoengine.errors import DoesNotExist
from omegaml.store import OmegaStore
from omegaml.util import override_settings, delete_database
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
import pandas as pd
import gridfs
from omegaml.documents import Metadata
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
        delete_database()
        disconnect('omega')

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

    def test_prefix_store(self):
        """
        this is to test if store prefixes work
        """
        df = pd.DataFrame({
            'a': range(1, 10),
            'b': range(1, 10)
        })
        datasets = OmegaStore(prefix='teststore')
        models = OmegaStore(prefix='models', kind=Metadata.SKLEARN_JOBLIB)
        datasets.put(df, 'test')
        self.assertEqual(len(datasets.list()), 1)
        self.assertEqual(len(models.list()), 0)

    def test_custom_levels(self):
        """
        this is to test if custom path and levels can be provided ok
        """
        df = pd.DataFrame({
            'a': range(1, 10),
            'b': range(1, 10)
        })
        datasets = OmegaStore(prefix='data')
        models = OmegaStore(prefix='models', kind=Metadata.SKLEARN_JOBLIB)
        # directory-like levels
        datasets.put(df, 'data/is/mypath/test')
        datasets.put(df, 'data/is/mypath/test2')
        self.assertEqual(len(datasets.list('data/*/mypath/*')), 2)
        self.assertEqual(len(datasets.list('data/*/test')), 1)
        # namespace-like levels
        datasets.put(df, 'my.namespace.module.test')
        datasets.put(df, 'my.namespace.module.test2')
        self.assertEqual(len(datasets.list('*.module.*')), 2)
        self.assertEqual(len(datasets.list('*.module.test2')), 1)

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

    def test_put_dataframe_timestamp(self):
        # create some dataframe
        from datetime import datetime
        df = pd.DataFrame({
            'a': range(1, 10),
            'b': range(1, 10)
        })
        store = OmegaStore(prefix='')
        # -- check default timestamp
        now = datetime.utcnow()
        store.put(df, 'mydata', append=False, timestamp=True)
        df2 = store.get('mydata')
        _created = df2['_created'].astype(datetime).unique()[0].to_datetime()
        self.assertEqual(_created.replace(second=0, microsecond=0),
                         now.replace(second=0, microsecond=0))
        # -- check custom timestamp column, default value
        now = datetime.utcnow()
        store.put(df, 'mydata', append=False, timestamp='CREATED')
        df2 = store.get('mydata')
        _created = df2['CREATED'].astype(datetime).unique()[0].to_datetime()
        self.assertEqual(_created.replace(second=0, microsecond=0),
                         now.replace(second=0, microsecond=0))
        # -- check custom timestamp column, value as tuple
        now = datetime.utcnow() - timedelta(days=1)
        store.put(df, 'mydata', append=False, timestamp=('CREATED', now))
        df2 = store.get('mydata')
        _created = df2['CREATED'].astype(datetime).unique()[0].to_datetime()
        self.assertEqual(_created.replace(second=0, microsecond=0),
                         now.replace(second=0, microsecond=0))
        # set a day in the past to avoid accidentally creating the current
        # datetime in mongo
        now = datetime.now() - timedelta(days=1)
        store.put(df, 'mydata', timestamp=now, append=False)
        df2 = store.get('mydata')
        # compare the data
        _created = df2['_created'].astype(datetime).unique()[0].to_datetime()
        self.assertEqual(_created.replace(microsecond=0),
                         now.replace(microsecond=0))

    def test_get_dataframe_filter(self):
        # create some dataframe
        df = pd.DataFrame({
            'a': range(1, 10),
            'b': range(1, 10)
        })
        store = OmegaStore(prefix='')
        store.put(df, 'mydata')
        # filter in mongodb
        df2 = store.get('mydata', filter=dict(a__gt=1, a__lt=10))
        # filter local dataframe
        df = df[(df.a > 1) & (df.a < 10)].reset_index(drop='index')
        self.assertTrue(df.equals(df2), "expected dataframes to be equal")

    def test_get_dataframe_project(self):
        # create some dataframe
        df = pd.DataFrame({
            'a': range(1, 10),
            'b': range(1, 10)
        })
        store = OmegaStore(prefix='')
        store.put(df, 'mydata')
        # filter in mongodb
        df2 = store.get('mydata', columns=['a'])
        # filter local dataframe
        df = df[['a']]
        self.assertTrue(df.equals(df2), "expected dataframes to be equal")

    def test_put_dataframe_with_index(self):
        # create some dataframe
        df = pd.DataFrame({
            'a': range(1, 10),
            'b': range(1, 10)
        })
        store = OmegaStore(prefix='')
        store.put(df, 'mydata', index=['a', '-b'])
        idxs = list(store.collection('mydata').list_indexes())
        idx_names = map(lambda v: dict(v).get('name'), idxs)
        self.assertIn('asc_a__desc_b', idx_names)

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

    def test_put_python_dict_multiple(self):
        # create some data
        data = {
            'a': range(1, 10),
            'b': range(1, 10)
        }
        store = OmegaStore(prefix='')
        store.put(data, 'mydata')
        store.put(data, 'mydata')
        data2 = store.get('mydata')
        # we will have stored the same object twice
        self.assertEquals(data, data2[0])
        self.assertEquals(data, data2[1])

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
        self.assertIn(
            'store.dfgroup.datastore', store.mongodb.collection_names())
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
        # test for non-existent file raises exception
        meta = store.put(df2, 'foo_will_be_removed', as_hdf=True)
        file_id = store.fs.get_last_version(
            'store.foo_will_be_removed.hdf')._id
        store.fs.delete(file_id)
        self.assertRaises(
            gridfs.errors.NoFile, store.get, 'foo_will_be_removed')
        store2 = OmegaStore()
        # test hdf file is not there
        self.assertNotIn('hdfdf.hdf', store2.fs.list())

    def test_put_same_name(self):
        """ test if metadata is updated instead of a new created """
        data = {
            'a': range(1, 10),
            'b': range(1, 10)
        }
        df = pd.DataFrame(data)
        store = OmegaStore()
        # store the object
        meta = store.put(df, 'foo')
        # store it again
        meta2 = store.put(df, 'foo', append=False)
        # we should still have only one object in metadata
        self.assertEqual(meta.pk, meta2.pk)
        df2 = store.get('foo')
        self.assertTrue(df.equals(df2))

    def test_store_with_attributes(self):
        data = {
            'a': range(1, 10),
            'b': range(1, 10)
        }
        df = pd.DataFrame(data)
        store = OmegaStore()
        # store the object, no attributes
        meta = store.put(df, 'foo')
        meta = store.metadata('foo')
        self.assertEqual(meta.attributes, {})
        # update attributes
        meta = store.put(df, 'foo', append=False, attributes={'foo': 'bar'})
        meta = store.metadata('foo')
        self.assertEqual(meta.attributes, {'foo': 'bar'})
        meta = store.put(
            df, 'foo', append=False, attributes={'foo': 'bax',
                                                 'foobar': 'barbar'})
        meta = store.metadata('foo')
        self.assertEqual(meta.attributes, {'foo': 'bax',
                                           'foobar': 'barbar'})

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
        self.assertEqual(
            store.list('datadf'), [], 'expected the store to be empty')
        with self.assertRaises(DoesNotExist):
            store.drop('nxstore', force=False)
        try:
            store.drop('nxstore', force=True)
            raised = False
        except:
            raised = True
        self.assertFalse(raised)

    def test_list_raw(self):
        data = {
            'a': range(1, 10),
            'b': range(1, 10)
        }
        df = pd.DataFrame(data)
        store = OmegaStore()
        meta = store.put(df, 'hdfdf', as_hdf=True)
        # list with pattern
        entries = store.list(pattern='hdf*', raw=True)
        self.assertTrue(isinstance(entries[0], Metadata))
        self.assertEqual('hdfdf', entries[0].name)
        self.assertEqual(len(entries), 1)
        # list with regexp
        entries = store.list(regexp='hdf.*', raw=True)
        self.assertTrue(isinstance(entries[0], Metadata))
        self.assertEqual('hdfdf', entries[0].name)
        self.assertEqual(len(entries), 1)
        # list without pattern nor regexp
        entries = store.list('hdfdf', kind=Metadata.PANDAS_HDF, raw=True)
        self.assertTrue(isinstance(entries[0], Metadata))
        self.assertEqual('hdfdf', entries[0].name)
        self.assertEqual(len(entries), 1)
        # subset kind
        entries = store.list('hdfdf', raw=True, kind=Metadata.PANDAS_DFROWS)
        self.assertEqual(len(entries), 0)
        entries = store.list('hdfdf', raw=True, kind=Metadata.PANDAS_HDF)
        self.assertEqual(len(entries), 1)
