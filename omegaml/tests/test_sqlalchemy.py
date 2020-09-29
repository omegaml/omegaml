import os
from getpass import getuser
from unittest import TestCase

import pandas as pd
from pandas.util.testing import assert_frame_equal
from sqlalchemy.engine import Connection, create_engine, ResultProxy

from omegaml import Omega
from omegaml.backends.sqlalchemy import SQLAlchemyBackend
from omegaml.tests.util import OmegaTestMixin


class SQLAlchemyBackendTests(OmegaTestMixin, TestCase):
    def setUp(self):
        self.om = Omega()
        self.om.models.register_backend(SQLAlchemyBackend.KIND, SQLAlchemyBackend)
        self.clean()
        os.remove('test.db') if os.path.exists('test.db') else None

    def test_put_connection(self):
        """
        store generic sqlalchemy connection
        """
        om = self.om
        cnx = 'sqlite:///test.db'
        om.datasets.put(cnx, 'testsqlite', kind=SQLAlchemyBackend.KIND)
        self.assertIn('testsqlite', om.datasets.list())
        meta = om.datasets.metadata('testsqlite')
        self.assertEqual(meta.kind, SQLAlchemyBackend.KIND)
        conn = om.datasets.get('testsqlite', raw=True)
        self.assertIsInstance(conn, Connection)

    def test_put_connection_with_secrets(self):
        """
        store generic sqlalchemy connection
        """
        om = self.om
        cnx = 'sqlite:///{user}.db'
        om.datasets.put(cnx, 'testsqlite', kind=SQLAlchemyBackend.KIND)
        self.assertIn('testsqlite', om.datasets.list())
        meta = om.datasets.metadata('testsqlite')
        self.assertEqual(meta.kind, SQLAlchemyBackend.KIND)
        self.assertIn('secrets', meta.kind_meta)
        # no secrets
        with self.assertRaises(KeyError):
            om.datasets.get('testsqlite')
        # directly specified
        conn = om.datasets.get('testsqlite', raw=True, secrets=dict(user='user'))
        # via vault
        om.datasets.put(dict(userid=getuser(), user='foobar'), '_omega/vault', append=False)
        conn = om.datasets.get('testsqlite', raw=True)
        self.assertIsInstance(conn, Connection)

    def test_put_connection_with_sql(self):
        """
        store generic sqlalchemy connection with sql, same principle as a view
        """
        om = self.om
        cnx_str = 'sqlite:///test.db'
        engine = create_engine(cnx_str)
        cnx = engine.connect()
        df = pd.DataFrame({
            'x': range(10)
        })
        df.to_sql('foobar', cnx, if_exists='replace', index=False)
        om.datasets.put(cnx_str, 'foobar',
                        sql='select * from foobar',
                        kind=SQLAlchemyBackend.KIND)
        self.assertIn('foobar', om.datasets.list())
        meta = om.datasets.metadata('foobar')
        self.assertEqual(meta.kind, SQLAlchemyBackend.KIND)
        dfx = om.datasets.get('foobar')
        assert_frame_equal(dfx, df)

    def test_put_connection_with_sql_vars(self):
        """
        store generic sqlalchemy connection with sql containing variables
        """
        om = self.om
        cnx_str = 'sqlite:///test.db'
        engine = create_engine(cnx_str)
        cnx = engine.connect()
        df = pd.DataFrame({
            'x': range(10)
        })
        df.to_sql('foobar', cnx, if_exists='replace', index=False)
        om.datasets.put(cnx_str, 'foobar',
                        sql='select {cols} from foobar',
                        kind=SQLAlchemyBackend.KIND)
        self.assertIn('foobar', om.datasets.list())
        meta = om.datasets.metadata('foobar')
        self.assertEqual(meta.kind, SQLAlchemyBackend.KIND)
        with self.assertRaises(KeyError):
            # missing sqlvars
            dfx = om.datasets.get('foobar')
        dfx = om.datasets.get('foobar', sqlvars=dict(cols='x'))
        assert_frame_equal(dfx, df)

    def test_put_connection_with_sql_vars_lazy(self):
        """
        store generic sqlalchemy connection with sql containing variables
        """
        om = self.om
        cnx_str = 'sqlite:///test.db'
        engine = create_engine(cnx_str)
        cnx = engine.connect()
        df = pd.DataFrame({
            'x': range(10)
        })
        df.to_sql('foobar', cnx, if_exists='replace', index=False)
        om.datasets.put(cnx_str, 'foobar',
                        sql='select {cols} from foobar',
                        kind=SQLAlchemyBackend.KIND)
        self.assertIn('foobar', om.datasets.list())
        meta = om.datasets.metadata('foobar')
        self.assertEqual(meta.kind, SQLAlchemyBackend.KIND)
        with self.assertRaises(KeyError):
            # missing sqlvars
            dfx = om.datasets.get('foobar')
        dfx = om.datasets.getl('foobar', sqlvars=dict(cols='x'))
        self.assertIsInstance(dfx, ResultProxy)

    def test_put_copy_from_connection(self):
        """
        store generic sqlalchemy connection
        """
        om = self.om
        cnx_str = 'sqlite:///test.db'
        engine = create_engine(cnx_str)
        cnx = engine.connect()
        df = pd.DataFrame({
            'x': range(10)
        })
        df.to_sql('foobar', cnx, if_exists='replace', index=False)
        om.datasets.put(cnx_str, 'foobar_copy',
                        copy=True,
                        sql='select * from foobar',
                        kind=SQLAlchemyBackend.KIND)
        self.assertIn('foobar_copy', om.datasets.list())
        meta = om.datasets.metadata('foobar_copy')
        self.assertEqual(meta.kind, 'pandas.dfrows')
        dfx = om.datasets.get('foobar_copy')
        assert_frame_equal(dfx, df)

    def test_put_connection_with_sql_no_index(self):
        """
        store sql alchemy connection to specific query
        """
        # -- no index, will use default to_sql, which is 'index'
        df = pd.DataFrame({
            'x': range(10)
        })
        self._test_put_connection_with_sql_index(df, index_names=None)

    def test_put_connection_with_sql_default_index(self):
        """
        store store connection to specific query with default index name
        """
        # -- specify the default index explicitely
        df = pd.DataFrame({
            'x': range(10)
        })
        self._test_put_connection_with_sql_index(df, index_names=['index'])

    def test_put_connection_with_sql_custom_index(self):
        """
        store store connection to specific query with custom index name
        """
        # -- specify a custom index name
        df = pd.DataFrame({
            'x': range(10)
        })
        self._test_put_connection_with_sql_index(df, index_names=['idx'])

    def _test_put_connection_with_sql_index(self, df, index_names=None):
        om = self.om
        cnx_str = 'sqlite:///test.db'
        engine = create_engine(cnx_str)
        cnx = engine.connect()
        if index_names:
            df.index.names = index_names
        df.to_sql('foobar', cnx, if_exists='replace', index=index_names is not None)
        # store connection string
        sql = "select * from foobar"
        om.datasets.put(cnx_str, 'testsqlite', kind=SQLAlchemyBackend.KIND,
                        sql=sql, index_columns=index_names)
        self.assertIn('testsqlite', om.datasets.list())
        meta = om.datasets.metadata('testsqlite')
        self.assertEqual(meta.kind, SQLAlchemyBackend.KIND)
        # get back the connection only
        conn = om.datasets.get('testsqlite', raw=True)
        self.assertIsInstance(conn, Connection)
        # get back data using the stored sql
        dfx = om.datasets.get('testsqlite')
        assert_frame_equal(dfx, df)

    def test_put_data_via_connection(self):
        """
        store dataframe via connection
        """
        om = self.om
        cnx = 'sqlite:///test.db'
        om.datasets.put(cnx, 'testsqlite', table=':foo',
                        kind=SQLAlchemyBackend.KIND)
        df = pd.DataFrame({
            'x': range(10)
        })
        df.index.names = ['index']
        # replace
        om.datasets.put(df, 'testsqlite', insert=True, append=False)
        meta = om.datasets.metadata('testsqlite')
        self.assertEqual(meta.kind, SQLAlchemyBackend.KIND)
        dfx = om.datasets.get('testsqlite', sql='select * from foo')
        assert_frame_equal(df, dfx)
        # append
        om.datasets.put(df, 'testsqlite', insert=True, append=False)
        om.datasets.put(df, 'testsqlite', insert=True)
        dfx = om.datasets.get('testsqlite', sql='select * from foo')
        df_expected = df.append(df)
        assert_frame_equal(dfx, df_expected)

    def test_put_data_via_connection_bucket(self):
        """
        store dataframe via connection
        """
        om = self.om['mybucket']
        cnx = 'sqlite:///test.db'
        om.datasets.put(cnx, 'testsqlite', table='foo',
                        kind=SQLAlchemyBackend.KIND)
        df = pd.DataFrame({
            'x': range(10)
        })
        df.index.names = ['index']
        # replace
        om.datasets.put(df, 'testsqlite', insert=True, append=False)
        meta = om.datasets.metadata('testsqlite')
        self.assertEqual(meta.kind, SQLAlchemyBackend.KIND)
        dfx = om.datasets.get('testsqlite', sql='select * from mybucket_foo')
        assert_frame_equal(df, dfx)
        # append
        om.datasets.put(df, 'testsqlite', insert=True, append=False)
        om.datasets.put(df, 'testsqlite', insert=True)
        dfx = om.datasets.get('testsqlite', sql='select * from mybucket_foo')
        df_expected = df.append(df)
        assert_frame_equal(dfx, df_expected)

    def test_put_raw_data_via_connection(self):
        """
        store raw dict via connection
        """
        om = self.om
        # store connection
        cnx = 'sqlite:///test.db'
        om.datasets.put(cnx, 'testsqlite', table=':foo',
                        kind=SQLAlchemyBackend.KIND)
        df = pd.DataFrame({
            'x': range(10)
        })
        df.index.names = ['index']
        raw = df.to_dict('dict')
        # replace
        om.datasets.put(raw, 'testsqlite', insert=True, append=False)
        meta = om.datasets.metadata('testsqlite')
        self.assertEqual(meta.kind, SQLAlchemyBackend.KIND)
        self.assertEqual(meta.kind_meta.get('table'), ':foo')
        dfx = om.datasets.get('testsqlite', sql='select * from foo')
        assert_frame_equal(df, dfx)
        # append
        om.datasets.put(raw, 'testsqlite', insert=True, append=False)
        om.datasets.put(raw, 'testsqlite', insert=True)
        dfx = om.datasets.get('testsqlite', sql='select * from foo')
        df_expected = df.append(df)
        assert_frame_equal(dfx, df_expected)
