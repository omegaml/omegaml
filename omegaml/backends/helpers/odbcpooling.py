"""
omegaml object helper for selecting datasets to reset odbc connection pooling

This resolves an issue with low-frequency access to SQL Server causing intermittent connection
drops. (OperationalError: ('HY000', "[HY000] [Microsoft][ODBC Driver 18 for SQL Server]
TCP Provider: Error code 0x2b (2) (SQLDriverConnect)"))

Background:

- The ODBC Driver error is due to a rare constellation where the ODBC connection has been idle for
  longer than 3600 seconds. SQLAlchemy is configured to issue a connection ping (SELECT 1) to validate
  the connection is still active. However, subsequent queries may still fail due to some network component
  dropping the connection, despite the successful SELECT 1.

- This helper resets the connection pool on all SQLAlchemy datasets, and ensures a new connection pool
  is created for matching the prefix filter. It can be adapted to other datasets or other types of filters,
  if required.

- To include or exclude a specific dataset, within or outside of the prefix filter, set the object's
  Metadata.attributes['sqlalchemy_clear'] = True | False (where True means to reset the connection pool).
  False means to reuse the existing connection pool. Defaults to False.

- To change parameters of the connection pool, set helper's Meta.attributes['pool_recycle'] = seconds.
  To set the prefixes, set helper's meta.attributes['prefixes'] = ['/prefix', ...], or [] to disable keep=False

Args:
    method (string): 'get', 'put', 'drop', depending on the method called (on.datasets.get/put/drop)
    meta (Metadata): the metadata of the object
    store (OmegaStore): the store, here on.dataset
    backend (BackedBackend): the object's backend instance
    **kwargs (dict): any other kwargs passed to the on.datasets.get/put/drop method

Returns:
    result (DataFrame|Connection|None): for method == 'get', the result of the backend.get() call; for
    all other methods None, the object helper mixin will call the backend directly.
"""
import time

from omegaml.backends.virtualobj import virtualobj


@virtualobj
def helper(*args, method=None, meta=None, store=None, backend=None, **kwargs):
    import omegaml as om
    on = om.datasets
    on.logger.debug(f"helper called with {method=} {store=} {backend=} {kwargs=}")
    # options
    prefixes = ['/sql']
    pool_recycle = 1800  # 30 minutes

    def get_helper_config():
        # get helper config
        # -- ensure helper metadata can be read ok subsequently, due to metadata caching
        helper_meta = om.datasets.metadata('.helpers/odbcpooling')
        helper_meta.gridfile.seek(0) if helper_meta is not None else None
        # --read config
        cfg_prefixes = helper_meta.attributes.get('prefixes', prefixes)
        cfg_pool_recycle = helper_meta.attributes.get('pool_recycle', pool_recycle)
        return cfg_prefixes, cfg_pool_recycle

    def should_reset_connection_pool():
        # have already applied the connection pool recycle fix?
        from omegaml.backends.sqlalchemy import ENGINE_KWARGS
        return ENGINE_KWARGS.get('pool_recycle', pool_recycle) != pool_recycle

    def reset_connection_pool():
        # resetting all connections, in all pools
        from omegaml.backends.sqlalchemy import ENGINE_KWARGS, SQLAlchemyBackend
        # from omegaml.backends.sqlalchemy import ENGINE_KWARGS, SQLAlchemyBackend
        # reset sqlalchemy pooling parameters to better defaults
        # retry to avoid intermittent errors, then rebuild connection pool
        for i in range(5):
            try:
                on.logger.debug('resetting connection pool')
                # disable pyodbc pooling to avoid pyodbc / sqlalchemy pooling interference
                import pyodbc
                pyodbc.pooling = False
                ENGINE_KWARGS.update(pool_pre_ping=True, pool_recycle=pool_recycle)
                SQLAlchemyBackend._SQLAlchemyBackend__CNX_CACHE.clear()  # noqa
                # keep-false clears the sqlalchemy engine pool for matching datasets
                # -- any future connections will be fresh. We try multiple times to clear caches
                # -- this adds a small delay on initial connections
                backend.get(meta.name, keep=False, sql='select 1')
            except Exception as e:
                on.logger.error(f'reset_connection_pool() failed on attempt {i} due to {e}')
                time.sleep(.001)
            else:
                break

    def dataset_preping():
        # on.datasets.get() with implied keep=False to ensure a fresh connection
        on.logger.debug('resetting odbc pooling for {meta.name}')
        # usual get, remove any kwargs not recognized by sqlalchemy dataset
        [kwargs.pop('keep', None) for k in dict(kwargs)
         if k not in "sql,chunksize,raw,sqlvars,secret,index,keep,lazy,table,trusted".split(',')]
        # reset connection pool with retry for this dataset, ensure a new connection can be established
        # since we have a new pool, pre ping is not issued by sqlalchemy, so we do it
        for i in range(5):
            try:
                backend.get(meta.name, keep=False, sql='select 1')
            except Exception as e:
                on.logger.error(f'get with fresh connection() on {meta.name} failed on attempt {i} due to {e}')
            else:
                break

    prefixes, pool_recycle = get_helper_config()
    reset_connection_pool() if should_reset_connection_pool() else None

    if method == 'get':
        if (any(meta.name.startswith(p) for p in prefixes)
                or meta.attributes.get('sqlalchemy_clear', False)):
            dataset_preping()

    # returning None triggers the default backend processing
    return None


def install():
    import omegaml as om
    # as_source=True ensures this helper works across all Python versions
    om.datasets.put(helper, 'helpers/odbcpooling', supports='kind:sqlalchemy.*', replace=True, as_source=True)
