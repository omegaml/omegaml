from __future__ import absolute_import

import unittest
import uuid
from datetime import timedelta
from unittest import skip

import gridfs
import joblib
import pandas as pd
from mongoengine.connection import disconnect
from mongoengine.errors import DoesNotExist, FieldDoesNotExist
from pandas.util import testing
from pandas.util.testing import assert_frame_equal, assert_series_equal
from six import BytesIO
from six.moves import range
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression, LinearRegression

from omegaml.backends.rawdict import PandasRawDictBackend
from omegaml.backends.rawfiles import PythonRawFileBackend
from omegaml.backends.scikitlearn import ScikitLearnBackend
from omegaml.documents import MDREGISTRY, Metadata
from omegaml.mdataframe import MDataFrame
from omegaml.notebook.jobs import OmegaJobs
from omegaml.store import OmegaStore
from omegaml.store.combined import CombinedOmegaStoreMixin
from omegaml.store.queryops import humanize_index
from omegaml.util import delete_database, json_normalize


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
        store = OmegaStore()
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression(solver='liblinear', multi_class='auto')
        lr.fit(X, Y)
        result = lr.predict(X)
        # package locally
        backend = ScikitLearnBackend(model_store=store,
                                     data_store=store)
        # v2 of the ScikitLearnBackend no longer supports testing these methods
        # test put(), get() instead
        zipfname = backend._v1_package_model(lr, 'models/foo')
        # load it, try predicting
        lr2 = backend._v1_extract_model(zipfname)
        self.assertIsInstance(lr2, LogisticRegression)
        result2 = lr2.predict(X)
        self.assertTrue((result == result2).all())

    def test_put_model(self):
        # create a test model
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression(solver='liblinear', multi_class='auto')
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
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        })
        datasets = OmegaStore(prefix='teststore')
        models = OmegaStore(prefix='models', kind=MDREGISTRY.SKLEARN_JOBLIB)
        datasets.put(df, 'test')
        self.assertEqual(len(datasets.list()), 1)
        self.assertEqual(len(models.list()), 0)

    def test_custom_levels(self):
        """
        this is to test if custom path and levels can be provided ok
        """
        df = pd.DataFrame({
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        })
        datasets = OmegaStore(prefix='data')
        models = OmegaStore(prefix='models', kind=MDREGISTRY.SKLEARN_JOBLIB)
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
        lr = LogisticRegression(solver='liblinear', multi_class='auto')
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
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        })
        store = OmegaStore(prefix='')
        store.put(df, 'mydata')
        df2 = store.get('mydata')
        self.assertTrue(df.equals(df2), "expected dataframes to be equal")

    def test_put_dataframe_multiple(self):
        # create some dataframe
        df = pd.DataFrame({
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        })
        store = OmegaStore(prefix='')
        store.put(df, 'mydata')
        df2 = store.get('mydata')
        self.assertTrue(df.equals(df2), "expected dataframes to be equal")
        # add again
        store.put(df, 'mydata')
        df2 = store.get('mydata')
        self.assertEqual(len(df) * 2, len(df2), "expected dataframes to be equal")

    def test_put_dataframe_xtra_large(self):
        # create some dataframe
        # force fast insert
        df = pd.DataFrame({
            'a': list(range(0, int(1e4 + 1))),
            'b': list(range(0, int(1e4 + 1)))
        })
        store = OmegaStore(prefix='')
        store.put(df, 'mydata')
        df2 = store.get('mydata')
        self.assertTrue(df.equals(df2), "expected dataframes to be equal")

    def test_put_dataframe_timestamp(self):
        # create some dataframe
        from datetime import datetime
        df = pd.DataFrame({
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        })
        store = OmegaStore(prefix='')
        # -- check default timestamp
        now = datetime.utcnow()
        store.put(df, 'mydata', append=False, timestamp=True)
        df2 = store.get('mydata')
        _created = pd.to_datetime(df2['_created'].unique()[0])
        self.assertEqual(_created.replace(second=0, microsecond=0),
                         now.replace(second=0, microsecond=0))
        # -- check custom timestamp column, default value
        now = datetime.utcnow()
        store.put(df, 'mydata', append=False, timestamp='CREATED')
        df2 = store.get('mydata')
        _created = pd.to_datetime(df2['CREATED'].unique()[0])
        self.assertEqual(_created.replace(second=0, microsecond=0),
                         now.replace(second=0, microsecond=0))
        # -- check custom timestamp column, value as tuple
        now = datetime.utcnow() - timedelta(days=1)
        store.put(df, 'mydata', append=False, timestamp=('CREATED', now))
        df2 = store.get('mydata')
        _created = pd.to_datetime(df2['CREATED'].unique()[0])
        self.assertEqual(_created.replace(second=0, microsecond=0),
                         now.replace(second=0, microsecond=0))
        # set a day in the past to avoid accidentally creating the current
        # datetime in mongo
        now = datetime.now() - timedelta(days=1)
        store.put(df, 'mydata', timestamp=now, append=False)
        df2 = store.get('mydata')
        # compare the data
        _created = pd.to_datetime(df2['_created'].unique()[0])
        self.assertEqual(_created.replace(microsecond=0),
                         now.replace(microsecond=0))

    def test_get_dataframe_filter(self):
        # create some dataframe
        df = pd.DataFrame({
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        })
        store = OmegaStore(prefix='')
        store.put(df, 'mydata')
        # filter in mongodb
        df2 = store.get('mydata', filter=dict(a__gt=1, a__lt=10))
        # filter local dataframe
        df = df[(df.a > 1) & (df.a < 10)]
        self.assertTrue(df.equals(df2), "expected dataframes to be equal")

    def test_get_dataframe_project(self):
        # create some dataframe
        df = pd.DataFrame({
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        })
        store = OmegaStore(prefix='')
        store.put(df, 'mydata')
        # filter in mongodb
        df2 = store.get('mydata', columns=['a'])
        # filter local dataframe
        df = df[['a']]
        self.assertTrue(df.equals(df2), "expected dataframes to be equal")

    def test_get_dataframe_projected_mixin(self):
        # create some dataframe
        df = pd.DataFrame({
            'a': list(range(1, 10)),
            'b': list(range(1, 10)),
            'c': list(range(1, 10)),
        })
        store = OmegaStore(prefix='')
        store.put(df, 'mydata')
        # filter in mongodb
        specs = ['a', ':b', ':', 'b:', '^c']
        for spec in specs:
            name_spec = 'mydata[{}]'.format(spec)
            df2 = store.get(name_spec)
            # filter local dataframe
            if spec == ':':
                dfx = df.loc[:, :]
            elif ':' in spec:
                from_col, to_col = spec.split(':')
                slice_ = slice(from_col or None, to_col or None)
                dfx = df.loc[:, slice_]
            elif spec.startswith('^'):
                spec_cols = spec[1:].split(',')
                cols = [col for col in df.columns if col not in spec_cols]
                dfx = df[cols]
            else:
                dfx = df[[spec]]
            self.assertTrue(dfx.equals(df2), "expected dataframes to be equal")

    def test_get_dataframe_opspec(self):
        # create some dataframe
        df = pd.DataFrame({
            'a': list(range(1, 10)),
            'b': list(range(1, 10)),
            'c': list(range(1, 10)),
        })
        store = OmegaStore(prefix='')
        store.put(df, 'mydata')
        # check # op returns iterchunks by default
        value = store.get('mydata#')
        self.assertTrue(hasattr(value, '__next__'))
        nvalue = next(value)
        self.assertEqual(len(nvalue), len(df))
        assert_frame_equal(nvalue, df)
        # check we can specify specific operator
        value = store.get('mydata#iterchunks')
        nvalue = next(value)
        self.assertTrue(hasattr(value, '__next__'))
        self.assertEqual(len(nvalue), len(df))
        assert_frame_equal(nvalue, df)
        # check we can specify kwargs
        value = store.get('mydata#iterchunks:chunksize=1')
        self.assertTrue(hasattr(value, '__next__'))
        self.assertEqual(len(next(value)), 1)
        value = store.get('mydata#iterchunks:chunksize=2')
        self.assertTrue(hasattr(value, '__next__'))
        self.assertEqual(len(next(value)), 2)
        # check we can use rows op as equiv of .iloc[start:end]
        value = store.get('mydata#rows:start=2,end=4')
        self.assertTrue(hasattr(value, '__next__'))
        self.assertEqual(len(next(value)), 2)
        # same as .iloc[start:end]
        value = store.get('mydata#rows:start=2,end=3')
        self.assertTrue(hasattr(value, '__next__'))
        assert_frame_equal(next(value), df.iloc[2:3])

    def test_get_dataframe_colspec_opspec(self):
        # create some dataframe
        df = pd.DataFrame({
            'a': list(range(1, 10)),
            'b': list(range(1, 10)),
            'c': list(range(1, 10)),
        })
        store = OmegaStore(prefix='')
        store.put(df, 'mydata')
        # check we can specify [] and # qualifiers
        value = store.get('mydata[a]#')
        self.assertTrue(hasattr(value, '__next__'))
        nvalue = next(value)
        self.assertEqual(len(nvalue), len(df))
        assert_frame_equal(nvalue, df[['a']])
        # check we can specify specific operator
        value = store.get('mydata[a,b]#iterchunks')
        nvalue = next(value)
        self.assertTrue(hasattr(value, '__next__'))
        self.assertEqual(len(nvalue), len(df))
        assert_frame_equal(nvalue, df[['a', 'b']])
        # check we can specify kwargs
        value = store.get('mydata[a,b]#iterchunks:chunksize=1')
        nvalue = next(value)
        self.assertTrue(hasattr(value, '__next__'))
        self.assertEqual(len(nvalue), 1)
        assert_frame_equal(nvalue, df[['a', 'b']].iloc[0:1])

    def test_put_dataframe_with_index(self):
        # create some dataframe
        df = pd.DataFrame({
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        })
        store = OmegaStore(prefix='')
        store.put(df, 'mydata', index=['a', '-b'])
        idxs = store.collection('mydata').index_information()
        idx_names = humanize_index(idxs)
        self.assertIn('asc__id_asc_a_desc_b_asc__idx#0_0_asc__om#rowid', idx_names)

    def test_put_dataframe_timeseries(self):
        # create some dataframe
        tsidx = pd.date_range(pd.datetime(2016, 1, 1), pd.datetime(2016, 4, 1))
        df = pd.DataFrame({
            'a': list(range(0, len(tsidx))),
            'b': list(range(0, len(tsidx)))
        }, index=tsidx)
        store = OmegaStore(prefix='')
        store.put(df, 'mydata')
        dfx = store.get('mydata')
        assert_frame_equal(df, dfx)
        idxs = store.collection('mydata').index_information()
        idx_names = humanize_index(idxs)
        self.assertIn('asc__id_asc__idx#0_0_asc__om#rowid', idx_names)

    def test_put_dataframe_multiindex(self):
        # create some dataframe
        store = OmegaStore(prefix='')
        midx = pd.MultiIndex(levels=[[u'bar', u'baz', u'foo', u'qux'],
                                     [u'one', u'two']],
                             codes=[
                                 [0, 0, 1, 1, 2, 2, 3, 3],
                                 [0, 1, 0, 1, 0, 1, 0, 1]],
                             names=[u'first', u'second'])
        df = pd.DataFrame({'x': range(0, len(midx))}, index=midx)
        store.put(df, 'mydata')
        dfx = store.get('mydata')
        assert_frame_equal(df, dfx)
        idxs = store.collection('mydata').index_information()
        idx_names = humanize_index(idxs)
        self.assertIn('asc__id_asc__idx#0_first_asc__idx#1_second_asc__om#rowid', idx_names)

    def test_put_python_dict(self):
        # create some data
        data = {
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        }
        store = OmegaStore(prefix='')
        store.put(data, 'mydata')
        data2 = store.get('mydata')
        self.assertEquals([data], data2)

    def test_put_python_dict_multiple(self):
        # create some data
        data = {
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
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
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        }
        meta = store.put(data, 'data')
        data2 = store.get('data', force_python=True)
        self.assertEqual(data, data2)
        # dataframe
        # create some dataframe
        df = pd.DataFrame({
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        })
        store.put(df, 'mydata')
        df2 = store.get('mydata', force_python=True)
        df2 = pd.DataFrame(df2)
        real_cols = [col for col in df2.columns
                     if (col != '_id'
                         and not col.startswith('_idx')
                         and not col.startswith('_om'))]
        df2 = df2[real_cols]
        self.assertTrue(df.equals(df2), "expected dataframes to be equal")
        # model
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression(solver='liblinear', multi_class='auto')
        lr.fit(X, Y)
        # store it remote
        store.put(lr, 'foox', _kind_version='1')
        # get it back as a zipfile
        lr2file = store.get('foox', force_python=True)
        lr_ = joblib.load(lr2file)
        self.assertIsInstance(lr_, LogisticRegression)

    def test_store_with_metadata(self):
        om = OmegaStore(prefix='')
        # dict
        data = {
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
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
        assert_frame_equal(df, df2)
        # model
        lr = LogisticRegression(solver='liblinear', multi_class='auto')
        meta = om.put(lr, 'mymodel', attributes=attributes)
        self.assertEqual(meta.kind, 'sklearn.joblib')
        self.assertEqual(meta.attributes, attributes)
        lr2 = om.get('mymodel')
        self.assertIsInstance(lr2, LogisticRegression)

    def test_store_metadata_notstrict(self):
        """ ensure Metadata attributes are not strictly checked

        this is to allow metadata extensions between omegaml versions
        """
        om = OmegaStore(prefix='')
        # dict
        data = {
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        }
        attributes = {'foo': 'bar'}
        meta = om.put(data, 'data', attributes=attributes)
        meta_collection = om.mongodb['metadata']
        flt = {'name': 'data'}
        meta_entry = meta_collection.find_one(flt)
        meta_entry['modified_extra'] = meta_entry['modified']
        meta_collection.replace_one(flt, meta_entry)
        try:
            meta = om.metadata('data')
        except FieldDoesNotExist:
            not_raised = False
        else:
            not_raised = True
        self.assertTrue(not_raised)

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
            'omegaml.dfgroup.datastore', store.mongodb.collection_names())
        # note column order can differ due to insertion order since pandas 0.25.1
        # hence using [] to ensure same column order for both expected, result
        df2 = store.get('dfgroup', kwargs={'b': 1})
        self.assertTrue(df2.equals(result_df[df2.columns]))
        df3 = store.get('dfgroup')
        self.assertTrue(df3.equals(df[df3.columns]))
        df4 = store.get('dfgroup', kwargs={'a': 1})
        self.assertTrue(df4.equals(result_df[df4.columns]))

    def test_store_dataframe_as_hdf(self):
        data = {
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        }
        df = pd.DataFrame(data)
        store = OmegaStore()
        meta = store.put(df, 'foo', as_hdf=True)
        self.assertEqual(meta.kind, 'pandas.hdf')
        # make sure the hdf file is actually there
        self.assertIn('omegaml.foo.hdf', store.fs.list())
        df2 = store.get('foo')
        self.assertTrue(df.equals(df2), "dataframes differ")
        # test for non-existent file raises exception
        meta = store.put(df2, 'foo_will_be_removed', as_hdf=True)
        file_id = store.fs.get_last_version(
            'omegaml.foo_will_be_removed.hdf')._id
        store.fs.delete(file_id)
        self.assertRaises(
            gridfs.errors.NoFile, store.get, 'foo_will_be_removed')
        store2 = OmegaStore()
        # test hdf file is not there
        self.assertNotIn('hdfdf.hdf', store2.fs.list())

    def test_put_same_name(self):
        """ test if metadata is updated instead of a new created """
        data = {
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        }
        df = pd.DataFrame(data)
        store = OmegaStore()
        # store the object
        meta = store.put(df, 'foo')
        # store it again
        meta2 = store.put(df, 'foo', append=False)
        # we should still have a new object in metadata
        # and the old should be gone
        self.assertNotEqual(meta.pk, meta2.pk)
        # Meta is to silence lint on import error
        Meta = store._Metadata
        metas = Meta.objects(name='foo', prefix=store.prefix,
                             bucket=store.bucket).all()
        self.assertEqual(len(metas), 1)
        df2 = store.get('foo')
        self.assertTrue(df.equals(df2))

    def test_put_append_false(self):
        """ test if we can create a new dataframe without previous metadata """
        data = {
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        }
        df = pd.DataFrame(data)
        store = OmegaStore()
        # store the object
        unique_name = uuid.uuid4().hex
        meta = store.put(df, unique_name, append=False)
        self.assertEqual(meta['name'], unique_name)

    def test_store_with_attributes(self):
        data = {
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        }
        df = pd.DataFrame(data)
        store = OmegaStore()
        # store the object, no attributes
        meta = store.put(df, 'foo', append=False)
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
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
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
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        }
        df = pd.DataFrame(data)
        store = OmegaStore()
        meta = store.put(df, 'hdfdf', as_hdf=True)
        # list with pattern
        entries = store.list(pattern='hdf*', raw=True)
        self.assertTrue(isinstance(entries[0], store._Metadata))
        self.assertEqual('hdfdf', entries[0].name)
        self.assertEqual(len(entries), 1)
        # list with regexp
        entries = store.list(regexp='hdf.*', raw=True)
        self.assertTrue(isinstance(entries[0], store._Metadata))
        self.assertEqual('hdfdf', entries[0].name)
        self.assertEqual(len(entries), 1)
        # list without pattern nor regexp
        entries = store.list('hdfdf', kind=MDREGISTRY.PANDAS_HDF, raw=True)
        self.assertTrue(isinstance(entries[0], store._Metadata))
        self.assertEqual('hdfdf', entries[0].name)
        self.assertEqual(len(entries), 1)
        # subset kind
        entries = store.list('hdfdf', raw=True, kind=MDREGISTRY.PANDAS_DFROWS)
        self.assertEqual(len(entries), 0)
        entries = store.list('hdfdf', raw=True, kind=MDREGISTRY.PANDAS_HDF)
        self.assertEqual(len(entries), 1)

    def test_lazy_unique(self):
        """ test getting a MDataFrame and unique values """
        data = {
            'a': list(range(1, 10)),
            'b': list(range(1, 10))
        }
        df = pd.DataFrame(data)
        store = OmegaStore()
        meta = store.put(df, 'foo', append=False)
        val = store.get('foo', lazy=True).a.unique().value
        self.assertListEqual(data['a'], list(val))

    def test_store_series(self):
        """ test storing a pandas series with it's own index """
        from string import ascii_lowercase
        series = pd.Series(range(10), index=(c for c in ascii_lowercase[0:10]))
        store = OmegaStore()
        store.put(series, 'fooseries', append=False)
        series2 = store.get('fooseries')
        assert_series_equal(series, series2)

    def test_store_named_series(self):
        """ test storing a pandas series with it's own index """
        from string import ascii_lowercase
        series = pd.Series(range(10),
                           name='foo',
                           index=(c for c in ascii_lowercase[0:10]))
        store = OmegaStore()
        store.put(series, 'fooseries', append=False)
        series2 = store.get('fooseries')
        assert_series_equal(series, series2)

    def test_store_series_timeindex(self):
        """ test storing a pandas series with it's own index """
        series = pd.Series(range(10),
                           name='foo',
                           index=pd.date_range(pd.datetime(2016, 1, 1),
                                               pd.datetime(2016, 1, 10)))
        store = OmegaStore()
        store.put(series, 'fooseries', append=False)
        series2 = store.get('fooseries')
        assert_series_equal(series, series2)

    def test_store_irregular_column_names(self):
        """ test storing irregular column names """
        df = pd.DataFrame({'x_1': range(10)})
        store = OmegaStore()
        store.put(df, 'foo', append=False)
        df2 = store.get('foo')
        self.assertEqual(df.columns, df2.columns)

    def test_store_datetime(self):
        """ test storing naive datetimes """
        df = pd.DataFrame({
            'x': pd.date_range(pd.datetime(2016, 1, 1),
                               pd.datetime(2016, 1, 10))
        })
        store = OmegaStore()
        store.put(df, 'test-date', append=False)
        df2 = store.get('test-date')
        testing.assert_frame_equal(df, df2)

    def test_store_tz_datetime(self):
        """ test storing timezoned datetimes """
        df = pd.DataFrame({
            'y': pd.date_range('2019-10-01', periods=5, tz='US/Eastern', normalize=True)
        })
        store = OmegaStore()
        store.put(df, 'test-date', append=False)
        df2 = store.get('test-date')
        testing.assert_frame_equal(df, df2)

    # TODO support DST-crossing datetime objects. use UTC to avoid the issue
    @skip('date ranges across dst period start/end do not return the original DatetimeIndex values')
    def test_store_tz_datetime_dst(self):
        """ test storing timezoned datetimes """
        # 2019 11 03 02:00 is the end of US DST https://www.timeanddate.com/time/dst/2019.html
        # pymongo will transform the object into a naive dt at UTC time at +3h (arguably incorrectly so)
        # while pandas creates the Timestamp as UTC -4 (as the day starts at 00:00, not 02:00).
        # On rendering back to a tz-aware datetime, this yields the wrong date (1 day eaerlier) because
        # pandas applies -4 on converting from UTC to US/Eastern (correctly).
        df = pd.DataFrame({
            'y': pd.date_range('2019-11-01', periods=5, tz='US/Eastern', normalize=True)
        })
        store = OmegaStore()
        store.put(df, 'test-date', append=False)
        df2 = store.get('test-date')
        # currently this fails, see @skip reason
        testing.assert_frame_equal(df, df2)

    def test_store_dict_in_df(self):
        df = pd.DataFrame({
            'x': [{'foo': 'bar '}],
        })
        store = OmegaStore()
        store.put(df, 'test-dict', append=False)
        df2 = store.get('test-dict')
        testing.assert_frame_equal(df, df2)

    def test_existing_arbitrary_collection_flat(self):
        data = {'foo': 'bar',
                'bax': 'fox'}
        store = OmegaStore()
        store.register_backend(PandasRawDictBackend.KIND, PandasRawDictBackend)
        foo_coll = store.mongodb['foo']
        foo_coll.insert(data)
        store.make_metadata('myfoo', collection='foo', kind='pandas.rawdict').save()
        self.assertIn('myfoo', store.list())
        # test we get back _id column if raw=True
        data_df = store.get('myfoo', raw=True)
        data_raw = store.collection('myfoo').find_one()
        assert_frame_equal(json_normalize(data_raw), data_df)
        # test we get just the data column
        data_ = store.get('myfoo', raw=False)
        cols = ['foo', 'bax']
        assert_frame_equal(json_normalize(data)[cols], data_[cols])

    def test_existing_arbitrary_collection_nested(self):
        data = {'foo': 'bar',
                'bax': {
                    'fox': 'fax',
                }}
        store = OmegaStore()
        store.register_backend(PandasRawDictBackend.KIND, PandasRawDictBackend)
        foo_coll = store.mongodb['foo']
        foo_coll.insert(data)
        store.make_metadata('myfoo', collection='foo', kind='pandas.rawdict').save()
        self.assertIn('myfoo', store.list())
        # test we get back _id column if raw=True
        data_df = store.get('myfoo', raw=True)
        data_raw = store.collection('myfoo').find_one()
        assert_frame_equal(json_normalize(data_raw), data_df)
        # test we get just the data column
        data_ = store.get('myfoo', raw=False)
        cols = ['foo', 'bax.fox']
        assert_frame_equal(json_normalize(data)[cols], data_[cols])

    def test_existing_arbitrary_collection_mdataframe(self):
        data = {'foo': 'bar',
                'bax': {
                    'fox': 'fax',
                }}
        store = OmegaStore()
        store.register_backend(PandasRawDictBackend.KIND, PandasRawDictBackend)
        foo_coll = store.mongodb['foo']
        foo_coll.insert(data)
        store.make_metadata('myfoo', collection='foo', kind='pandas.rawdict').save()
        self.assertIn('myfoo', store.list())
        # test we get back _id column if raw=True
        mdf = store.getl('myfoo', raw=True)
        self.assertIsInstance(mdf, MDataFrame)
        data_df = mdf.value
        data_raw = store.collection('myfoo').find_one()
        assert_frame_equal(json_normalize(data_raw), data_df)
        # test we get just the data column
        mdf = store.getl('myfoo', raw=False)
        self.assertIsInstance(mdf, MDataFrame)
        data_df = mdf.value
        data_raw = store.collection('myfoo').find_one()
        cols = ['foo', 'bax.fox']
        assert_frame_equal(json_normalize(data)[cols], data_df[cols])

    def test_arbitrary_collection_new(self):
        data = {'foo': 'bar',
                'bax': 'fox'}
        store = OmegaStore()
        store.register_backend(PandasRawDictBackend.KIND, PandasRawDictBackend)
        # create the collection
        foo_coll = store.mongodb['foo']
        foo_coll.insert(data)
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

    def test_raw_files(self):
        store = OmegaStore()
        store.register_backend(PythonRawFileBackend.KIND, PythonRawFileBackend)
        # test we can write from a file-like object
        data = "some data"
        file_like = BytesIO(data.encode('utf-8'))
        store.put(file_like, 'myfile')
        self.assertEqual(data.encode('utf-8'), store.get('myfile').read())
        # test we can write from an actual file
        data = "some other data"
        file_like = BytesIO(data.encode('utf-8'))
        with open('/tmp/testfile.txt', 'wb') as fout:
            fout.write(file_like.read())
        store.put('/tmp/testfile.txt', 'myfile')
        self.assertEqual(data.encode('utf-8'), store.get('myfile').read())

    def test_bucket(self):
        # test different buckets actually separate objects by the same name
        # -- data
        foo_store = OmegaStore(bucket='foo')
        bar_store = OmegaStore(bucket='bar')
        foo_store.register_backend(PythonRawFileBackend.KIND, PythonRawFileBackend)
        bar_store.register_backend(PythonRawFileBackend.KIND, PythonRawFileBackend)
        foo_data = {'foo': 'bar',
                    'bax': 'fox'}
        bar_data = {'foo': 'bax',
                    'bax': 'foz'}
        foo_store.put(foo_data, 'data')
        bar_store.put(bar_data, 'data')
        self.assertEqual(foo_store.get('data')[0], foo_data)
        self.assertEqual(bar_store.get('data')[0], bar_data)
        # -- files
        foo_data = "some data"
        file_like = BytesIO(foo_data.encode('utf-8'))
        foo_store.put(file_like, 'myfile')
        bar_data = "some other data"
        file_like = BytesIO(bar_data.encode('utf-8'))
        bar_store.put(file_like, 'myfile')
        self.assertNotEqual(foo_store.get('myfile').read(), bar_store.get('myfile').read())

    def test_hidden_temp_handling(self):
        foo_store = OmegaStore(bucket='foo')
        foo_store.put({}, '_temp')
        self.assertNotIn('_temp', foo_store.list(include_temp=False))
        self.assertIn('_temp', foo_store.list(include_temp=True))
        foo_store.put({}, '.hidden')
        self.assertNotIn('.hidden', foo_store.list(hidden=False))
        self.assertIn('.hidden', foo_store.list(hidden=True))

    def test_help(self):
        foo_store = OmegaStore(bucket='foo')
        obj = {}
        foo_store.put(obj, '_temp')
        # get backend for different signatures
        backend_name = foo_store._resolve_help_backend('_temp')
        backend_obj = foo_store._resolve_help_backend(obj)
        self.assertEqual(backend_name, backend_obj)
        self.assertIsInstance(backend_obj, OmegaStore)
        # get backend for scikit model
        reg = LinearRegression()
        foo_store.put(reg, 'regmodel')
        backend_name = foo_store._resolve_help_backend('regmodel')
        backend_obj = foo_store._resolve_help_backend(reg)
        self.assertIsInstance(backend_name, ScikitLearnBackend)
        self.assertIsInstance(backend_obj, ScikitLearnBackend)

    def test_combined_store(self):
        foo_store = OmegaStore(bucket='foo', prefix='foo/')
        bar_store = OmegaStore(bucket='bar', prefix='bar/')
        job_store = OmegaJobs(bucket='bar', prefix='jobs/')
        obj = {}
        foo_store.put(obj, 'obj')
        obj = {}
        bar_store.put(obj, 'obj')
        combined = CombinedOmegaStoreMixin([foo_store, bar_store, job_store])
        # list
        contents = combined.list()
        self.assertIn('foo/obj', contents)
        self.assertIn('bar/obj', contents)
        # get back
        for member in contents:
            self.assertEqual(combined.get(member), [obj])
            meta = combined.metadata(member)
            self.assertIsInstance(meta, Metadata)
            self.assertEqual(meta.kind, 'python.data')
            self.assertEqual(meta.name, member.split('/', 1)[1])



