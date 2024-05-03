from hashlib import sha256

import warnings

from getpass import getuser
from unittest import TestCase

import os
import pandas as pd
from omegaml import Omega
from omegaml.backends.sqlalchemy import SQLAlchemyBackend
from omegaml.tests.util import OmegaTestMixin
from pandas.testing import assert_frame_equal
from sqlalchemy.engine import Connection, create_engine, ResultProxy

from omegaml.util import signature


class SQLAlchemyBackendTests(OmegaTestMixin, TestCase):
    def setUp(self):
        self.om = Omega()
        self.om.models.register_backend(SQLAlchemyBackend.KIND, SQLAlchemyBackend)
        self.clean()
        os.remove('../test.db') if os.path.exists('../test.db') else None

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
        # -- test missing key values do not raise KeyError
        om.datasets.defaults.OMEGA_FOOBAR = '{othervalue}'
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
        om.datasets.put(dict(userid=getuser(), user='foobar'), '.omega/vault', append=False)
        conn = om.datasets.get('testsqlite', raw=True)
        self.assertIsInstance(conn, Connection)

    def test_connection_cache(self):
        """ test connection caching
        """
        from omegaml.backends import sqlalchemy
        om = self.om
        cnx = 'sqlite:///{user}.db'
        om.datasets.put(cnx, 'testsqlite', kind=SQLAlchemyBackend.KIND)
        conn = om.datasets.get('testsqlite', raw=True, secrets=dict(user='user'), keep=True)
        conn_ = om.datasets.get('testsqlite', raw=True, secrets=dict(user='user'), keep=True)
        self.assertEqual(conn.engine, conn_.engine)
        # drop should clear cache
        om.datasets.drop('testsqlite', secrets=dict(user='user'))
        conn_ = om.datasets.get('testsqlite', raw=True, secrets=dict(user='user'), keep=True)
        self.assertIsNone(conn_)
        self.assertTrue(len(sqlalchemy.SQLAlchemyBackend._SQLAlchemyBackend__CNX_CACHE) == 0)
        # even if we drop without secrets, cache is cleared
        om.datasets.put(cnx, 'testsqlite', kind=SQLAlchemyBackend.KIND)
        om.datasets.get('testsqlite', raw=True, secrets=dict(user='user'), keep=True)
        om.datasets.drop('testsqlite')
        self.assertTrue(len(sqlalchemy.SQLAlchemyBackend._SQLAlchemyBackend__CNX_CACHE) == 0)

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
                        sql='select {{cols}} from foobar',
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
        # using
        om.datasets.put(cnx_str, 'foobar',
                        sql='select {{cols}} from foobar',
                        kind=SQLAlchemyBackend.KIND)
        self.assertIn('foobar', om.datasets.list())
        meta = om.datasets.metadata('foobar')
        self.assertEqual(meta.kind, SQLAlchemyBackend.KIND)
        with self.assertRaises(KeyError):
            # missing sqlvars
            dfx = om.datasets.get('foobar')
        dfx = om.datasets.getl('foobar', sqlvars=dict(cols='x as x'))
        self.assertIsInstance(dfx, ResultProxy)
        print(list(dfx))

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
        df_expected = pd.concat([df, df])
        assert_frame_equal(dfx, df_expected)

    def test_put_data_via_connection_bucket(self):
        """
        store dataframe via connection
        """
        self.clean('mybucket')
        om = self.om['mybucket']
        cnx = 'sqlite:///test.db'
        om.datasets.put(cnx, 'testsqlite', table='foo',
                        kind=SQLAlchemyBackend.KIND)
        meta = om.datasets.metadata('testsqlite')
        self.assertEqual(meta.kind, SQLAlchemyBackend.KIND)
        # try inserting via connection
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
        df_expected = pd.concat([df, df])
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
        df_expected = pd.concat([df, df])
        assert_frame_equal(dfx, df_expected)

    def test_query_in_clause(self):
        om = self.om
        cnx_str = 'sqlite:///test.db'
        engine = create_engine(cnx_str)
        cnx = engine.connect()
        df = pd.DataFrame({
            'x': range(10)
        })
        df.to_sql('foobar', cnx, if_exists='replace', index=False)
        om.datasets.put(cnx_str, 'foobar',
                        sql='select * from foobar where x in {x} or x in {y}',
                        kind=SQLAlchemyBackend.KIND)
        df_db = om.datasets.get('foobar', sqlvars={
            'x': [1, 2, 3],
            'y': [5, 6, 7]
        })
        fltx = df['x'].isin([1, 2, 3])
        flty = df['x'].isin([5, 6, 7])
        df_filtered = df[fltx | flty].reset_index(drop=True)
        assert_frame_equal(df_db, df_filtered)

    def test_put_connection_with_sql_injection(self):
        """
        attempt sql injection
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
                        sql='select * from foobar where x={x} and x > 5',
                        kind=SQLAlchemyBackend.KIND)
        self.assertIn('foobar', om.datasets.list())
        meta = om.datasets.metadata('foobar')
        self.assertEqual(meta.kind, SQLAlchemyBackend.KIND)
        # simulate sql injection
        # -- if injection is executed, will return all rows
        # -- if injection is not executed will return no rows
        #    (because no row matches the {x}="-1 or 0=0" statement)
        # -- the log statement prints the sql with {x} replaced as :x
        #    (:notation denotes bound variables)
        # -- the sqlvars are passed on to sqlalchemy.execute verbatim,
        #    i.e. are not interpreted as part of the sql statement
        injection = "-1 or 0=0 --"
        sqlvars = {'x': injection}
        with self.assertLogs('omegaml', level='DEBUG') as cm:
            dfx = om.datasets.get('foobar', sqlvars=sqlvars)
        self.assertEqual(len(dfx), 0)
        self.assertIn("select * from foobar where x=:x", str(cm.output))
        self.assertIn("{'x': '-1 or 0=0 --'}", str(cm.output))

    def test_trusted_sqlvars(self):
        om = self.om
        cnx_str = 'sqlite:///test.db'
        engine = create_engine(cnx_str)
        cnx = engine.connect()
        df = pd.DataFrame({
            'x': range(10)
        })
        df.to_sql('foobar', cnx, if_exists='replace', index=False)
        om.datasets.put(cnx_str, 'foobar',
                        sql='select * from foobar where x={{x}}',
                        kind=SQLAlchemyBackend.KIND)
        self.assertIn('foobar', om.datasets.list())
        meta = om.datasets.metadata('foobar')
        self.assertEqual(meta.kind, SQLAlchemyBackend.KIND)
        sqlvars = {'x': '1 or 0=0'}
        # we don't trust the sqlvars -- this will issue a warning
        for trusted in [False, True, None, sha256(str(sqlvars).encode('utf-8')).hexdigest()]:
            with warnings.catch_warnings(record=True) as wrn:
                dfx = om.datasets.get('foobar', sqlvars=sqlvars, trusted=trusted)
                self.assertEqual(len(dfx), 10)
                warnlog = str(list(w.message for w in wrn))
                self.assertIn('Statement >select * from foobar where x={x}< contains unsafe variables [\'x\']. Use :notation or sanitize input.', warnlog)
        # we trust the sqlvars -- no warning will be issued
        with warnings.catch_warnings(record=True) as wrn:
            dfx = om.datasets.get('foobar', sqlvars=sqlvars, trusted=signature(sqlvars))
            self.assertEqual(len(dfx), 10)
            warnlog = str(list(w.message for w in wrn))
            self.assertNotIn('Statement >select * from foobar where x={x}< contains unsafe variables [\'x\']. Use :notation or sanitize input.', warnlog)



