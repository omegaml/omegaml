from logging import warning

import logging
import os
import pandas as pd
import sqlalchemy
import string
import threading
import warnings
from getpass import getuser
from hashlib import sha256
from sqlalchemy.exc import StatementError
from urllib.parse import quote_plus

from omegaml.backends.basedata import BaseDataBackend
from omegaml.util import ProcessLocal, KeepMissing, tqdm_if_interactive, signature

try:
    import snowflake

    sql_logger = logging.getLogger('snowflake')
    sql_logger.setLevel('CRITICAL')
except:
    pass

#: override by setting om.defaults.SQLALCHEMY_ALWAYS_CACHE
ALWAYS_CACHE = True
# -- enabled by default as this is the least-surprised option
# -- consistent with sqlalchemy connection pooling defaults
#: kwargs for create_engine()
ENGINE_KWARGS = dict(echo=False, pool_pre_ping=True, pool_recycle=3600)
# -- echo=False - do not log to stdout
# -- pool_pre_ping=True - always check, re-establish connection if no longer working
# -- pool_recylce=N - do not reuse connections older than N seconds

logger = logging.getLogger(__name__)


class SQLAlchemyBackend(BaseDataBackend):
    """
    sqlalchemy plugin for omegaml

    Usage:

        Define your sqlalchemy connection::

            sqlalchemy_constr = f'sqlalchemy://{user}:{password}@{account}/'

        Store the connection in any of three ways::

            # -- just the connection
            om.datasets.put(sqlalchemy_constr, 'mysqlalchemy')
            om.datasets.get('mysqlalchemy', raw=True)
            => the sql connection object

            # -- store connection with a predefined sql
            om.datasets.put(sqlalchemy_constr, 'mysqlalchemy',
                            sql='select ....')
            om.datasets.get('mysqlalchemy')
            => will return a pandas dataframe using the specified sql to run.
               specify chunksize= to return an interable of dataframes

            # -- predefined sqls can contain variables to be resolved at access time
            #    if you miss to specify required variables in sqlvars, a KeyError is raised
            om.datasets.put(sqlaclhemy_constr, 'myview',
                            sql='select ... from T1 where col="{var}"')
            om.datasets.get('mysqlalchemy', sqlvars=dict(var="value"))

            # -- Variables are replaced by binding parameters, which is safe for
            #    untrusted inputs. To replace variables as strings, use double
            #    `{{variable}}` notation. A warning will be issued because this
            #    is considered an unsafe practice for untrusted input (REST API).
            #    It is in your responsibility to sanitize the value of the `cols` variable.
            om.datasets.put(sqlaclhemy_constr, 'myview',
                            sql='select {{cols}} from T1 where col="{var}"')
            om.datasets.get('mysqlalchemy', sqlvars=dict(cols='foo, bar',
                                                         var="value"))

        Query data from a connection and store into an omega-ml dataset::

            # -- copy the result of the sqlalchemy query to omegaml
            om.datasets.put(sqlalchemy_constr, 'mysqlalchemy',
                            sql='select ...', copy=True)
            om.datasets.get('mysqlalchemy')
            => will return a pandas dataframe (without executing any additional queries)
            => can also use with om.datasets.getl('mysqlalchemy') to return a MDataFrame

        Controlling the table used in the connection::

            # -- the default table is {bucket}_{name}, override using table='myname'
            om.datasets.put(sqlalchemy_constr, 'mysqlalchemy',
                            table='mytable',
                            sql='select ...',
                            copy=True)
            om.datasets.get('mysqlalchemy') # read from {bucket}_myname

            # -- to use a specific table, without bucket information use table=':myname'
            om.datasets.put(sqlalchemy_constr, 'mysqlalchemy',
                            table=':mytable',
                            sql='select ...',
                            copy=True)
            om.datasets.get('mysqlalchemy') # read from myname

        Inserting data via a previously stored connection::

            # -- store data back through the connection
            om.datasets.put(sqlalchemy_constr, 'mysqlalchemy')
            om.datasets.put(df, 'mysqlalchemy',
                            table='SOMETABLE')

        Using variables in connection strings:

        Connection strings may contain variables, e.g. userid and password.
        By default variables are resolved from the os environment. Can also
        specify using any dict.::

            # -- use connection string with variables
            sqlalchemy_constr = 'sqlite:///{dbname}.db'
            om.datasets.put(sqlalchemy_constr, 'userdb')
            om.datasets.get('userdb', secrets=dict(dbname='chuckdb'))

            # -- alternatively, create a vault dataset:
            secrets = dict(userid='chuck', dbname='chuckdb')
            om.datasets.put(secrets, '.omega/vault')
            om.datasets.get('userdb')

            the '.omega/vault' dataset will be queried using the current userid as
            the secret name, and the dbname retrieved from the document. This is
            experimental and the vault is not encrypted.

    Advanced:

        ``om.datasets.put()`` supports the following additional keyword arguments

        * ``chunksize=int`` - specify the number of rows to read from sqlalchemy in one chunk.
          defaults to 10000

        * ``parse_dates=['col', ...]`` - list of column names to parse for date, time or datetime.
          see pd.read_sql for details

        * ``transform=callable`` - a callable, is passed the DataFrame of each chunk before it
          is inserted into the database. use to provide custom transformations.
          only works on copy=True

        * any other kwargs supported by ``pandas.read_sql``

    """
    KIND = 'sqlalchemy.conx'
    PROMOTE = 'metadata'

    #: sqlalchemy.Engine cache to enable pooled connections
    __CNX_CACHE = ProcessLocal()

    # -- https://docs.sqlalchemy.org/en/14/core/pooling.html#module-sqlalchemy.pool
    # -- create_engine() must be called per-process, hence using ProcessLocal
    # -- meaning when using a multiprocessing.Pool or other fork()-ed processes,
    #    the cache will be cleared in child processes, forcing the engine to be
    #    recreated automatically in _get_connection

    @classmethod
    def supports(cls, obj, name, insert=False, data_store=None, model_store=None, *args, **kwargs):
        valid = cls._is_valid_url(cls, obj)
        support_via = cls._supports_via(cls, data_store, name, obj)
        return valid or support_via

    def drop(self, name, secrets=None, **kwargs):
        # ensure cache is cleared
        clear_cache = True if secrets is None else False
        try:
            self.get(name, secrets=secrets, raw=True, keep=False)
        except KeyError as e:
            warnings.warn(f'Connection cache was cleared, however secret {e} was missing.')
            clear_cache = True
        if clear_cache:
            self.__CNX_CACHE.clear()
        return super().drop(name, **kwargs)

    def sign(self, values):
        return signature(values)

    def get(self, name, sql=None, chunksize=None, raw=False, sqlvars=None,
            secrets=None, index=True, keep=None, lazy=False, table=None, trusted=False, *args, **kwargs):
        """ retrieve a stored connection or query data from connection

        Args:
            name (str): the name of the connection
            secrets (dict): dict to resolve variables in the connection string
            keep (bool): if True connection is kept open, defaults to True (change
              default by setting om.defaults.SQLALCHEMY_ALWAYS_CACHE = False)
            table (str): the name of the table, will be prefixed with the
               store's bucket name unless the table is specified as ':name'
            trusted (bool|str): if passed must be the value for store.sign(sqlvars or kwargs),
               otherwise a warning is issued for any remaining variables in the sql statement

        Returns:
            connection

        To query data and return a DataFrame, specify ``sql='select ...'``:

        Args:
                sql (str): the sql query, defaults to the query specific on .put()
                chunksize (int): the number of records for each chunk, if
                   specified returns an iterator
                sqlvars (dict): optional, if specified will be used to format sql

        Returns:
            pd.DataFrame

        To get the connection for a data query, instead of a DataFrame:

        Args:

                raw (bool): if True, returns the raw sql alchemy connection
                keep (bool): option, if True keeps the connection open. Lazy=True
                  implies keep=True. This is potentially unsafe in a multi-user
                  environment where connection strings contain user-specific
                  secrets. To always keep connections open, set
                  ``om.datasets.defaults.SQLALCHEMY_ALWAYS_CACHE=True``

        Returns:
            connection

        To get a cursor for a data query, instead of a DataFrame. Note this
        implies keep=True.

        Args:

                lazy (bool): if True, returns a cursor instead of a DataFrame
                sql (str): the sql query, defaults to the query specific on .put()

        Returns:
            cursor
        """
        meta = self.data_store.metadata(name)
        connection_str = meta.kind_meta.get('sqlalchemy_connection')
        valid_sql = lambda v: isinstance(v, str) or v is not None
        sql = sql if valid_sql(sql) else meta.kind_meta.get('sql')
        sqlvars = sqlvars or {}
        table = self._default_table(table or meta.kind_meta.get('table') or name)
        if not raw and not valid_sql(sql):
            sql = f'select * from :sqltable'
        chunksize = chunksize or meta.kind_meta.get('chunksize')
        _default_keep = getattr(self.data_store.defaults,
                                'SQLALCHEMY_ALWAYS_CACHE',
                                ALWAYS_CACHE)
        keep = keep if keep is not None else _default_keep
        if connection_str:
            secrets = self._get_secrets(meta, secrets)
            connection = self._get_connection(name, connection_str, secrets=secrets, keep=keep)
        else:
            raise ValueError('no connection string')
        if not raw and valid_sql(sql):
            sql = sql.replace(':sqltable', table)
            index_cols = _meta_to_indexcols(meta) if index else kwargs.get('index_col')
            stmt = self._sanitize_statement(sql, sqlvars, trusted=trusted)
            kwargs = meta.kind_meta.get('kwargs') or {}
            kwargs.update(kwargs)
            if not lazy:
                logger.debug(f'executing sql {stmt} with parameters {sqlvars}')
                pd_kwargs = {**dict(chunksize=chunksize, index_col=index_cols,
                                    params=(sqlvars or {})), **kwargs}
                result = pd.read_sql(stmt, connection, **pd_kwargs)
            else:
                # lazy returns a cursor
                logger.debug(f'preparing a cursor for sql {sql} with parameters {sqlvars}')
                result = connection.execute(stmt, **sqlvars)
                keep = True
            if not keep:
                connection.close()
            return result
        return connection

    def put(self, obj, name, sql=None, copy=False, append=True, chunksize=None,
            transform=None, table=None, attributes=None, insert=False,
            secrets=None, *args, **kwargs):
        """ store sqlalchemy connection or insert data into an existing connection

        Args:
            obj (str|pd.DataFrame): the sqlalchemy connection string or a dataframe object
            name (str): the name of the object
            table (str): optional, if specified is stored along connection
            sql (str): optional, if specified is stored along connection
            copy (bool): optional, if True the connection is queried using sql
                and the resulting data is stored instead, see below
            attributes (dict): optional, set or update metadata.attributes

        Returns:
            metadata of the stored connection

        Instead of inserting the connection specify ``copy=True`` to query data
        and store it as a DataFrame dataset given by ``name``:

        Args:
            sql (str): sql to query
            append (bool): if True the data is appended if exists already
            chunksize (int): number of records to query in each chunk
            transform (callable): passed as DataFrame.to_sql(method=)

        Returns:
            metadata of the inserted dataframe

        To insert data via a previously stored connection, specify ``insert=True``:

        Args:
            insert (bool): specify True to insert via the connection
            table (str): the table name to use for inserting data
            append (bool): if False will replace any existing table, defaults to True
            index (bool): if False will not attempt to create an index in target, defaults to False
            chunksize (int): number of records to insert in each chunk

        Returns:
            metadata of the connection
        """
        meta = self.data_store.metadata(name)
        if not insert and self._is_valid_url(obj):
            # store a connection object
            url = obj
            cnx_name = name if not copy else '_cnx_{}'.format(name)
            table = self._default_table(table or name)
            metadata = self._put_as_connection(url, cnx_name, sql=sql, chunksize=chunksize,
                                               table=table, attributes=attributes, **kwargs)
            if copy:
                secrets = self._get_secrets(metadata, secrets)
                metadata = self._put_as_data(url, name, cnx_name,
                                             sql=sql, chunksize=chunksize,
                                             append=append, transform=transform,
                                             secrets=secrets,
                                             **kwargs)
        elif meta is not None:
            table = self._default_table(table or meta.kind_meta.get('table') or name)
            metadata = self._put_via(obj, name, append=append, table=table, chunksize=chunksize,
                                     transform=transform, **kwargs)
        else:
            raise ValueError('type {} is not supported by {}'.format(type(obj), self.KIND))
        metadata.attributes.update(attributes) if attributes else None
        return metadata.save()

    def _put_via(self, obj, name, append=True, table=None, chunksize=None, transform=None,
                 index_columns=None, index=True, **kwargs):
        # write data back through the connection
        # -- ensure we have a valid object
        if not hasattr(obj, 'to_sql'):
            warning('obj.to_sql() does not exist, trying pd.DataFrame(obj)')
            obj = pd.DataFrame(obj)
        # -- get the connection
        connection = self.get(name, raw=True)
        metadata = self.data_store.metadata(name)
        if isinstance(obj, pd.DataFrame) and index:
            index_cols = _dataframe_to_indexcols(obj, metadata, index_columns=index_columns)
        else:
            index_cols = index_columns
        metadata.kind_meta['index_columns'] = index_cols
        exists_action = 'append' if append else 'replace'
        transform = transform
        self._chunked_to_sql(obj, table, connection, chunksize=chunksize, method=transform,
                             if_exists=exists_action, index=index, index_label=index_cols, **kwargs)
        connection.close()
        return metadata

    def _put_as_data(self, url, name, cnx_name, sql=None, chunksize=None, append=True,
                     transform=None, **kwargs):
        # use the url to query the connection and store resulting data instead
        if not sql:
            raise ValueError('a valid SQL statement is required with copy=True')
        metadata = self.copy_from_sql(sql, url, name, chunksize=chunksize,
                                      append=append, transform=transform,
                                      **kwargs)
        metadata.attributes['created_from'] = cnx_name
        return metadata

    def _put_as_connection(self, url, name, sql=None, chunksize=None, attributes=None,
                           table=None, index_columns=None, secrets=None, **kwargs):
        kind_meta = {
            'sqlalchemy_connection': str(url),
            'sql': sql,
            'chunksize': chunksize,
            'table': ':' + table,
            'index_columns': index_columns,
            'kwargs': kwargs,
        }
        if secrets is True or (secrets is None and '{' in url and '}' in url):
            kind_meta['secrets'] = {
                'dsname': '.omega/vault',
                'query': {
                    'data_userid': '{user}'
                }
            }
        else:
            kind_meta['secrets'] = secrets
        metadata = self.data_store.metadata(name)
        if metadata is not None:
            metadata.kind_meta.update(kind_meta)
        else:
            metadata = self.data_store.make_metadata(name, self.KIND,
                                                     kind_meta=kind_meta,
                                                     attributes=attributes)
        return metadata.save()

    def _get_connection(self, name, connection_str, secrets=None, keep=False):
        from sqlalchemy import create_engine
        # passwords should be encoded
        # https://docs.sqlalchemy.org/en/13/core/engines.html#database-urls
        encoded = lambda d: {
            k: (quote_plus(v.decode('utf-8')) if isinstance(v, bytes)
                else quote_plus(v)) for k, v in d.items() if isinstance(v, (str, bytes))
        }
        connection = None
        cache_key = None
        try:
            # SECDEV: the cache key is a secret in order to avoid privilege escalation
            # -- if it is not secret, user A could create the connection (=> cache)
            # -- user B could reuse the connection by retrieving the dataset without secrets
            # -- this way the user needs to have the same secrets in order to reuse the connection
            enc_secrets = encoded(secrets or {})
            connection_str = connection_str.format(**enc_secrets)
            cache_key = sha256(f'{name}:{connection_str}'.encode('utf8')).hexdigest()
            engine = self.__CNX_CACHE.get(cache_key) or create_engine(connection_str, **ENGINE_KWARGS)
            connection = engine.connect()
        except KeyError as e:
            msg = ('{e}, ensure secrets are specified for connection '
                   '>{connection_str}<'.format(**locals()))
            raise KeyError(msg)
        except Exception as e:
            if connection is not None:
                connection.close()
                self.__CNX_CACHE.pop(cache_key, None)
            raise
        else:
            if keep:
                self.__CNX_CACHE[cache_key] = engine
            else:
                self.__CNX_CACHE.pop(cache_key, None)
        return connection

    def copy_from_sql(self, sql, connstr, name, chunksize=10000,
                      append=False, transform=None, secrets=None, **kwargs):
        connection = self._get_connection(name, connstr, secrets=secrets)
        chunksize = chunksize or 10000  # avoid None
        pditer = pd.read_sql(sql, connection, chunksize=chunksize, **kwargs)
        with tqdm_if_interactive().tqdm(unit='rows') as pbar:
            meta = self._chunked_insert(pditer, name, append=append,
                                        transform=transform, pbar=pbar)
        connection.close()
        return meta

    def _chunked_to_sql(self, df, table, connection, if_exists='append', chunksize=None, pbar=True, **kwargs):
        # insert large df in chunks and with a progress bar
        # from https://stackoverflow.com/a/39495229
        chunksize = chunksize if chunksize is not None else 10000

        def chunker(seq, size):
            return (seq.iloc[pos:pos + size] for pos in range(0, len(seq), size))

        def to_sql(df, table, connection, pbar=None):
            for i, cdf in enumerate(chunker(df, chunksize)):
                exists_action = if_exists if i == 0 else "append"
                cdf.to_sql(table, con=connection, if_exists=exists_action, **kwargs)
                if pbar:
                    pbar.update(len(cdf))
                else:
                    print("writing chunk {}".format(i))

        with tqdm_if_interactive().tqdm(total=len(df), unit='rows') as pbar:
            to_sql(df, table, connection, pbar=pbar)

    def _chunked_insert(self, pditer, name, append=True, transform=None, pbar=None):
        # insert into om dataset
        for i, df in enumerate(pditer):
            if pbar is not None:
                pbar.update(len(df))
            should_append = (i > 0) or append
            if transform:
                df = transform(df)
            try:
                meta = self.data_store.put(df, name, append=should_append)
            except Exception as e:
                rows = df.iloc[0:10].to_dict()
                raise ValueError("{e}: {rows}".format(**locals()))
        return meta

    def _is_valid_url(self, url):
        # enable subclass override
        return _is_valid_url(url)

    def _supports_via(self, data_store, name, obj):
        obj_ok = isinstance(obj, (pd.Series, pd.DataFrame, dict))
        if obj_ok and data_store:
            meta = data_store.metadata(name)
            same_kind = meta and meta.kind == self.KIND
            return obj_ok and same_kind
        return False

    def _get_secrets(self, meta, secrets):
        secrets_specs = meta.kind_meta.get('secrets')
        values = ({k:v for k, v in os.environ.items() if k.isupper() and isinstance(v, (str, bytes))}
                  if self.data_store.defaults.OMEGA_ALLOW_ENV_CONFIG else dict())
        values.update(**self.data_store.defaults)
        if not secrets and secrets_specs:
            dsname = secrets_specs['dsname']
            query = secrets_specs['query']
            # -- format query values
            query = _format_dict(query, replace=('_', '.'), **values, user=self._getuser())
            # -- run query
            secrets = self.data_store.get(dsname, filter=query)
            secrets = secrets[0] if isinstance(secrets, list) and len(secrets) == 1 else {}
            secrets.update(values)
        # -- format secrets
        if secrets:
            secrets = _format_dict(secrets, **values, user=self._getuser())
        return secrets

    def _getuser(self):
        return getattr(self.data_store.defaults, 'OMEGA_USERNAME', getuser())

    def _default_table(self, name):
        if name is None:
            return name
        if not name.startswith(':'):
            name = f'{self.data_store.bucket}_{name}'
        else:
            name = name[1:]
        return name

    def _sanitize_statement(self, sql, sqlvars, trusted=False):
        # sanitize sql:string statement in two steps
        # -- step 1: replace all {} variables by :notation
        # -- step 2: replace all remaining {} variables from sqlvars
        #    and issue a warning. step 2 is considered unsafe if
        #    the sqlvars source cannot be trusted
        # -- step 3: prepare a SQL statement with bound variables
        # see https://realpython.com/prevent-python-sql-injection/#using-query-parameters-in-sql
        if not isinstance(sql, str):
            return sql
        # replace all {...} variables with bound parameters
        #    sql = "select * from foo where user={username}"
        #       => "select * from foo where user=:username"
        placeholders = list(string.Formatter().parse(sql))
        vars = [spec[1] for spec in placeholders if spec[1]]
        safe_replacements = {var: f':{var}' for var in vars}
        sql = sql.format(**safe_replacements)
        # build parameter list for tuples and lists
        # -- sqlalchemy+pyodbc do not support lists of values
        # -- list of values must be passed as single parameters
        # -- e.g. sql=select * from x in :list
        #    =>       select * from x in (:x_1, :x_2, :x_3, ...)
        for k in vars:
            # note we are iterating vars, not sqlvars
            # -- sqlvars is not used in constructing sql text
            v = sqlvars[k]
            if isinstance(v, (list, tuple)):
                bind_vars = {f'{k}_{i}': lv for i, lv in enumerate(v)}
                placeholders = ','.join(f':{bk}' for bk in bind_vars)
                sql = sql.replace(f':{k}', f'({placeholders})')
                sqlvars.update(bind_vars)
        try:
            # format remaining {{}} for selection
            #    sql = "select {{cols}} from foo where user=:username
            #    =>    "select a, b from foo where user=:username
            placeholders = list(string.Formatter().parse(sql))
            vars = [spec[1] for spec in placeholders if spec[1]]
            if vars and trusted != self.sign(sqlvars):
                warnings.warn(f'Statement >{sql}< contains unsafe variables {vars}. Use :notation or sanitize input.')
            sql = sql.format(**{**sqlvars, **safe_replacements})
        except KeyError as e:
            raise KeyError('{e}, specify sqlvars= to build query >{sql}<'.format(**locals()))
        # prepare sql statement with bound variables
        try:
            stmt = sqlalchemy.sql.text(sql)
        except StatementError as exc:
            raise
        return stmt


def _is_valid_url(url):
    # check if we have a valid url with a registered backend
    import sqlalchemy

    try:
        url = sqlalchemy.engine.url.make_url(url)
        drivername = url.drivername.split('+')[0]  # e.g. mssql+pyodbc => mssql
        valid = url.drivername in sqlalchemy.dialects.__all__
        valid |= sqlalchemy.dialects.registry.load(drivername) is not None
    except:
        valid = False
    return valid


def _dataframe_to_indexcols(df, metadata, index_columns=None):
    # from a dataframe get index column names
    # works like pd.DataFrame.to_sql except for creating default index_i cols
    # for any missing (None) index labels in a MultiIndex.
    index_cols = metadata.kind_meta.get('index_columns') or index_columns or list(df.index.names)
    multi = isinstance(df.index, pd.MultiIndex)
    if index_cols is not None:
        for i, col in enumerate(index_cols):
            if col is None:
                index_cols[i] = 'index' if not multi else 'index_{}'.format(i)
    return index_cols


def _meta_to_indexcols(meta):
    index_cols = meta.kind_meta.get('index_columns')
    multi = isinstance(index_cols, (list, tuple)) and len(index_cols) > 1
    if index_cols is not None and not isinstance(index_cols, str):
        for i, col in enumerate(index_cols):
            if col is None:
                index_cols[i] = 'index' if not multi else 'index_{}'.format(i)
    return index_cols


def _format_dict(d, replace=None, **kwargs):
    for k, v in dict(d).items():
        if replace:
            del d[k]
            k = k.replace(*replace) if replace else k
        d[k] = v.format_map(KeepMissing(kwargs)) if isinstance(v, str) else v
    return d


def load_sql(om=None, kind=SQLAlchemyBackend.KIND):
    """
    load ipython sql magic, loading all sql alchemy connections

    Usage:
        !pip install ipython-sql

        # prepare some connection, insert some data
        df = pd.DataFrame(...)
        om.datasets.put('sqlite:///test.db', 'testdb')
        om.datasets.put(df, 'testdb', table='foobar', insert=True)

        from omegaml.backends.sqlalchemy import load_sql
        load_sql()

        # list registered connections
        %sql
            omsql://testdb

        # run queries
        %sql omsql://testdb select * from foobar

    See Also:
        https://pypi.org/project/ipython-sql/

    Args:
        om (Omega): optional, specify omega instance, defaults to om.setup()
        kind (str): the backend's kind, used to find connections to register
           with the sql magic

    Returns:
        None
    """
    from unittest.mock import MagicMock
    from IPython import get_ipython
    import omegaml as om
    from sql.connection import Connection # noqa

    class ConnectionShim:
        # this is required to trick sql magic into accepting existing connection objects
        # (by default sql magic expects connection strings, not connection objects)
        def __init__(self, url, conn):
            self.session = conn
            self.metadata = MagicMock()
            self.metadata.bind.url = url
            self.dialect = getattr(conn, 'dialect', 'omsql')

    # load sql magic
    ipython = get_ipython()
    ipython.magic('load_ext sql')
    # load registered sqlalchemy datasets
    om = om or om.setup()
    for ds in om.datasets.list(kind=kind, raw=True):
        cnxstr = 'omsql://{ds.name}'.format(**locals())
        conn = om.datasets.get(ds.name, raw=True)
        Connection.connections[cnxstr] = ConnectionShim(cnxstr, conn)
    ipython.magic('sql')
