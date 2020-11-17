from getpass import getuser
from logging import warning

import logging
import os
import pandas as pd
import six

from omegaml.backends.basedata import BaseDataBackend

try:
    import snowflake

    sql_logger = logging.getLogger('snowflake')
    sql_logger.setLevel('CRITICAL')
except:
    pass

CNX_CACHE = {}
ALWAYS_CACHE = False


class SQLAlchemyBackend(BaseDataBackend):
    """
    sqlalchemy plugin for omegaml

    Usage:
        # define your sqlalchemy connection
        sqlalchemy_constr = f'sqlalchemy://{user}:{password}@{account}/'

        Store in any of three ways:

        # -- just the connection
        om.datasets.put(sqlalchemy_constr, 'mysqlalchemy')
        om.datasets.get('mysqlalchemy', raw=True)
        => the sql connection object

        # -- store connection with a predefined sql
        om.datasets.put(sqlalchemy_constr, 'mysqlalchemy', sql='select ....')
        om.datasets.get('mysqlalchemy')
        => will return a pandas dataframe using the specified sql to run.
           specify chunksize= to return an interable of dataframes

        # -- predefined sqls can contain variables to be resolved at access time
        #    if you miss to specify required variables in sqlvars, a KeyError is raised
        om.datasets.put(sqlaclhemy_constr, 'myview', sql='select ... from col="{var}"')
        om.datasets.get('mysqlalchemy', sqlvars=dict(var="value"))

        Copy to an omega dataset from the connection

        # -- copy the result of the sqlalchemy query to omegaml
        om.datasets.put(sqlalchemy_constr, 'mysqlalchemy', sql='select ...', copy=True)
        om.datasets.get('mysqlalchemy')
        => will return a pandas dataframe (without executing any additional queries)
        => can also use with om.datasets.getl('mysqlalchemy') to return a MDataFrame

        # -- the default table when storing data is {bucket}_{name}, override using table='myname'
        om.datasets.put(sqlalchemy_constr, 'mysqlalchemy', table='mytable', sql='select ...', copy=True)
        om.datasets.get('mysqlalchemy') # read from {bucket}_myname
        # -- to use a specific table, without bucket information use table=':myname'
        om.datasets.put(sqlalchemy_constr, 'mysqlalchemy', table=':mytable', sql='select ...', copy=True)
        om.datasets.get('mysqlalchemy') # read from myname

        Insert data via the connection

        # -- store data back through the connection
        om.datasets.put(sqlalchemy_constr, 'mysqlalchemy')
        om.datasets.put(df, 'mysqlalchemy', table='SOMETABLE')

        Connection strings can contain variables, e.g. userid and password.
        By default variables are resolved from the os environment. Can also
        specify using any dict.

        # -- use connection string with variables
        sqlalchemy_constr = 'sqlite:///{dbname}.db'
        om.datasets.put(sqlalchemy_constr, 'userdb')
        om.datasets.get('userdb', secrets=dict(dbname='chuckdb'))

        # -- alternatively, create a vault dataset:
        secrets = dict(userid='chuck', dbname='chuckdb')
        om.datasets.put(secrets, '_omega/vault')
        om.datasets.get('userdb')

        the '_omega/vault' dataset will be queried using the current userid as
        the secret name,ad the dbname retrieved from the document. This is
        experimental and the vault is not encrypted.

    Advanced:

        om.datasets.put() supports the following additional keyword arguments

        chunksize=int   specify the number of rows to read from sqlalchemy in one chunk.
                        defaults to 10000

        parse_dates=['col', ...] list of column names to parse for date, time or datetime.
                        see pd.read_sql for details

        transform=callable  a callable, is passed the DataFrame of each chunk before it
                        is inserted into the database. use to provide custom transformations.
                        only works on copy=True

        as well as other kwargs supported by pd.read_sql

    """
    KIND = 'sqlalchemy.conx'

    @classmethod
    def supports(cls, obj, name, insert=False, data_store=None, model_store=None, *args, **kwargs):
        valid = cls._is_valid_url(cls, obj)
        support_via = cls._supports_via(cls, data_store, name, obj)
        return valid or support_via

    def drop(self, name, **kwargs):
        if name in CNX_CACHE:
            del CNX_CACHE[name]
        return super().drop(name, **kwargs)

    def get(self, name, sql=None, chunksize=None, raw=False, sqlvars=None,
            secrets=None, index=True, keep=False, lazy=False, table=None, *args, **kwargs):
        """
        retrieve connection or query data from connection

        Args:
            name (str): the name of the connection
            secrets (dict): dict to resolve variables in the connection string
            keep (bool): if True connection is kept open.
            table (str): the name of the table, will be prefixed with the store's bucket
               unless it is specified as ':name'

        Query data, specify sql='select ...':
            sql (str): the sql query, defaults to the query specific on .put()
            chunksize (int): the number of records for each chunk, if
               specified returns an iterator
            sqlvars (dict): optional, if specified will be used to format sql

        Get connection:
            raw (bool): the raw sql alchemy connection

        To reuse connections:
            specify keep=True. Note this is potentially unsafe in a multi-user
            environment where connection strings contain user-specific secrets.
            If you want to always keep connections open, specify
            om.datasets.defaults.SQLALCHEMY_ALWAYS_CACHE=True

        Returns:
            connection or pd.DataFrame
        """
        meta = self.data_store.metadata(name)
        connection_str = meta.kind_meta.get('sqlalchemy_connection')
        sql = sql or meta.kind_meta.get('sql')
        table = self._default_table(table or meta.kind_meta.get('table') or name)
        if not raw and not sql:
            sql = f'select * from {table}'
        chunksize = chunksize or meta.kind_meta.get('chunksize')
        keep = getattr(self.data_store.defaults, 'SQLALCHEMY_ALWAYS_CACHE',
                       ALWAYS_CACHE) or keep
        if connection_str:
            secrets = self._get_secrets(meta, secrets)
            connection = self._get_connection(name, connection_str, secrets=secrets, keep=keep)
        else:
            raise ValueError('no connection string')
        if not raw and sql:
            index_cols = _meta_to_indexcols(meta) if index else kwargs.get('index_col')
            try:
                sql = sql.format(**(sqlvars or {}))
            except KeyError as e:
                raise KeyError('{e}, specify sqlvars= to build query >{sql}<'.format(**locals()))
            kwargs = meta.kind_meta.get('kwargs') or {}
            kwargs.update(kwargs)
            if not lazy:
                result = pd.read_sql(sql, connection, chunksize=chunksize, index_col=index_cols, **kwargs)
            else:
                # lazy returns a cursor
                result = connection.execute(sql)
            if not keep:
                connection.close()
            return result
        return connection

    def put(self, obj, name, sql=None, copy=False, append=True, chunksize=None,
            transform=None, table=None, attributes=None, insert=False,
            secrets=None, *args, **kwargs):
        """
        store sqlalchemy connection or data into an existing connection

        Args:
            obj (str|pd.DataFrame): the sqlalchemy connection string or a dataframe object
            name (str): the name of the object
            table (str): optional, if specified is stored along connection
            sql (str): optional, if specified is stored along connection
            copy (bool): optional, if True the connection is queried using sql and the resulting data is stored instead,
                see Copying
            attributes (dict): optional, set or update metadata.attributes

        Copying data, specify copy=True:
            sql (str): sql to query
            append (bool): if True the data is appended if exists already
            chunksize (int): number of records to use
            transform (callable): passed as DataFrame.to_sql(method=)

        Inserting via connection, specify insert=True:
            insert (bool): specify True to insert via connection
            table (str): the table name to use for inserting data
            append (bool): if False will replace any existing table, defaults to True
            index (bool): if False will not attempt to create an index in target, defaults to False

        Returns:
            metadata
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
                self._put_as_data(url, name, cnx_name,
                                  sql=sql, chunksize=chunksize,
                                  append=append, transform=None,
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
                'dsname': '_omega/vault',
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

        connection = None
        try:
            connection_str = connection_str.format(**(secrets or {}))
            engine = create_engine(connection_str, echo=False)
            connection = CNX_CACHE.get(name) or engine.connect()
        except KeyError as e:
            msg = ('{e}, ensure secrets are specified for connection '
                   '>{connection_str}<'.format(**locals()))
            raise KeyError(msg)
        except Exception as e:
            if connection is not None:
                connection.close()
            raise
        else:
            if keep:
                CNX_CACHE[name] = connection
            else:
                if name in CNX_CACHE:
                    del CNX_CACHE[name]
        return connection

    def copy_from_sql(self, sql, connstr, name, chunksize=10000,
                      append=False, transform=None, secrets=None, **kwargs):
        connection = self._get_connection(name, connstr, secrets=secrets)
        chunksize = chunksize or 10000  # avoid None
        pditer = pd.read_sql(sql, connection, chunksize=chunksize, **kwargs)
        try:
            import tqdm
        except:
            meta = self._chunked_insert(pditer, name, append=append,
                                        transform=transform)
        else:
            with tqdm.tqdm(unit='rows') as pbar:
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

        def to_sql(df, table, connection, pbar=False):
            for i, cdf in enumerate(chunker(df, chunksize)):
                exists_action = if_exists if i == 0 else "append"
                cdf.to_sql(table, con=connection, if_exists=exists_action, **kwargs)
                if pbar:
                    pbar.update(len(cdf))
                else:
                    print("writing chunk {}".format(i))

        try:
            import tqdm
            if pbar is False:
                pbar = None
        except Exception as e:
            to_sql(df, table, connection, pbar=pbar)
        else:
            with tqdm.tqdm(total=len(df), unit='rows') as pbar:
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
        if not secrets and secrets_specs:
            dsname = secrets_specs['dsname']
            query = secrets_specs['query']
            # -- format query values
            query = _format_dict(query, replace=('_', '.'), **os.environ, user=getuser())
            # -- run query
            secrets = self.data_store.get(dsname, filter=query)
            secrets = secrets[0] if isinstance(secrets, list) and len(secrets) == 1 else {}
            secrets.update(os.environ)
        # -- format secrets
        if secrets:
            secrets = _format_dict(secrets, **os.environ, user=getuser())
        return secrets

    def _default_table(self, name):
        if name is None:
            return name
        if not name.startswith(':'):
            name = f'{self.data_store.bucket}_{name}'
        else:
            name = name[1:]
        return name


def _is_valid_url(url):
    # check if we have a valid url with a registered backend
    import sqlalchemy

    try:
        url = sqlalchemy.engine.url.make_url(url)
        drivername = url.drivername.split('+')[0] # e.g. mssql+pyodbc => mssql
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
    if index_cols is not None and not isinstance(index_cols, six.string_types):
        for i, col in enumerate(index_cols):
            if col is None:
                index_cols[i] = 'index' if not multi else 'index_{}'.format(i)
    return index_cols


def _format_dict(d, replace=None, **kwargs):
    for k, v in dict(d).items():
        if replace:
            del d[k]
            k = k.replace(*replace) if replace else k
        d[k] = v.format(**kwargs)
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
    from sql.connection import Connection

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
