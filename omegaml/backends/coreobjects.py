import os
import tempfile
from datetime import datetime

import gridfs
from mongoengine import GridFSProxy

from omegaml.backends.basedata import BaseDataBackend
from omegaml.documents import MDREGISTRY
from omegaml.store import MongoQueryOps, Filter
from omegaml.store.fastinsert import fast_insert, default_chunksize
from omegaml.store.queryops import sanitize_filter
from omegaml.util import is_dataframe, is_series, is_ndarray, ensure_index, unravel_index, jsonescape, \
    cursor_to_dataframe, convert_dtypes, restore_index, signature, make_tuple, mongo_compatible


class CoreObjectsBackend(BaseDataBackend):
    """ Provides Python and pandas basic types storage

    Notes:
        * to stay backwards compatible, the backend uses KIND="core.object", however the actual
          Metadata.kind used for various objects are defined in omegaml.documents.MDREGISTRY as PANDAS_DFROWS,
          PANDAS_SEROWS, PANDAS_DFGROUP, PYTHON_DATA, PANDAS_HDF

    .. versionadded:: NEXT
        refactored from omegaml.store.base.OmegaStore
    """
    KIND = "core.object"
    # additional kinds registered in store.defaults.OMEGA_STORE_BACKENDS
    # -- see OmegaStore.register_backend()
    KIND_EXT = (MDREGISTRY.PANDAS_DFROWS, MDREGISTRY.PANDAS_SEROWS, MDREGISTRY.PANDAS_DFGROUP,
                MDREGISTRY.PYTHON_DATA, MDREGISTRY.PANDAS_HDF)

    @classmethod
    def supports(self, obj, name, **kwargs):
        return is_dataframe(obj) | is_series(obj) | is_ndarray(obj) | isinstance(obj, (dict, list, tuple))

    def get(self, name, version=-1, force_python=False, lazy=False, **kwargs):
        meta = self.store.metadata(name, version=version)
        if meta.kind == MDREGISTRY.PANDAS_DFROWS:
            return self.get_dataframe_documents(name, version=version, lazy=lazy, **kwargs)
        elif meta.kind == MDREGISTRY.PANDAS_SEROWS:
            return self.get_dataframe_documents(name, version=version, lazy=lazy, is_series=True, **kwargs)

        elif meta.kind == MDREGISTRY.PANDAS_DFGROUP:
            return self.get_dataframe_dfgroup(name, version=version, lazy=lazy, **kwargs)
        elif meta.kind == MDREGISTRY.PYTHON_DATA:
            return self.get_python_data(name, version=version, lazy=lazy, **kwargs)
        elif meta.kind == MDREGISTRY.PANDAS_HDF:
            return self.get_dataframe_hdf(name, version=version)
        return self.get_object_as_python(meta, version=version)

    def put(self, obj, name, attributes=None, **kwargs):
        if is_dataframe(obj) or is_series(obj):
            groupby = kwargs.get('groupby')
            if obj.empty:
                from warnings import warn
                warn(
                    'Provided dataframe is empty, ignoring it, doing nothing here!')
                return None
            if kwargs.pop('as_hdf', False):
                return self.put_dataframe_as_hdf(
                    obj, name, attributes, **kwargs)
            elif groupby:
                return self.put_dataframe_as_dfgroup(
                    obj, name, groupby, attributes)
            append = kwargs.pop('append', None)
            timestamp = kwargs.pop('timestamp', None)
            index = kwargs.pop('index', None)
            chunksize = kwargs.pop('chunksize', default_chunksize)
            return self.put_dataframe_as_documents(
                obj, name, append=append, attributes=attributes, index=index,
                timestamp=timestamp, chunksize=chunksize, **kwargs)
        elif is_ndarray(obj):
            if kwargs.pop('as_pydata', False):
                return self.put_pyobj_as_document(obj.tolist(), name,
                                                  attributes=attributes, **kwargs)
            return self.put_ndarray_as_hdf(obj, name, attributes=attributes,
                                           **kwargs)
        elif isinstance(obj, (dict, list, tuple)):
            kwargs.pop('as_pydata', None)
            if kwargs.pop('as_hdf', False):
                return self.put_pyobj_as_hdf(obj, name,
                                             attributes=attributes, **kwargs)
            return self.put_pyobj_as_document(obj, name,
                                              attributes=attributes, **kwargs)
        raise TypeError('type %s not supported' % type(obj))

    @property
    def collection(self):
        return self.data_store.collection

    @property
    def store(self):
        return self.data_store

    def put_dataframe_as_documents(self, obj, name, append=None,
                                   attributes=None, index=None,
                                   timestamp=None, chunksize=None,
                                   ensure_compat=True, _fast_insert=fast_insert,
                                   **kwargs):
        """
        store a dataframe as a row-wise collection of documents

        :param obj: the dataframe to store
        :param name: the name of the item in the store
        :param append: if False collection will be dropped before inserting,
           if True existing documents will persist. Defaults to True. If not
           specified and rows have been previously inserted, will issue a
           warning.
        :param index: list of columns, using +, -, @ as a column prefix to
           specify ASCENDING, DESCENDING, GEOSPHERE respectively. For @ the
           column has to represent a valid GeoJSON object.
        :param timestamp: if True or a field name adds a timestamp. If the
           value is a boolean or datetime, uses _created as the field name.
           The timestamp is always datetime.datetime.utcnow(). May be overriden
           by specifying the tuple (col, datetime).
        :param ensure_compat: if True attempt to convert obj to mongodb compatibility,
           set to False only if you are sure to have only compatible values in dataframe.
           defaults to True. False may reduce memory and increase speed on large dataframes.
        :return: the Metadata object created
        """
        import pandas as pd
        collection = self.collection(name)
        if is_series(obj):
            import pandas as pd
            obj = pd.DataFrame(obj, index=obj.index, columns=[str(obj.name)])
            store_series = True
        else:
            store_series = False
        if append is False:
            self.drop(name, force=True)
        elif append is None and collection.count_documents({}, limit=1):
            from warnings import warn
            warn('%s already exists, will append rows' % name)
        if index:
            # get index keys
            if isinstance(index, dict):
                idx_kwargs = index
                index = index.pop('columns')
            else:
                idx_kwargs = {}
            # create index with appropriate options
            keys, idx_kwargs = MongoQueryOps().make_index(index, **idx_kwargs)
            ensure_index(collection, keys, **idx_kwargs)
        if timestamp:
            dt = datetime.utcnow()
            if isinstance(timestamp, bool):
                col = '_created'
            elif isinstance(timestamp, str):
                col = timestamp
            elif isinstance(timestamp, datetime):
                col, dt = '_created', timestamp
            elif isinstance(timestamp, tuple):
                col, dt = timestamp
            else:
                col = '_created'
            obj[col] = dt
        # store dataframe indicies
        # FIXME this may be a performance issue, use size stored on stats or metadata
        row_count = self.collection(name).estimated_document_count()
        # fixes #466, ensure column names are strings in a multiindex
        if isinstance(obj.columns, pd.MultiIndex):
            obj.columns = obj.columns.map('_'.join)
        obj, idx_meta = unravel_index(obj, row_count=row_count)
        stored_columns = [jsonescape(col) for col in obj.columns]
        column_map = list(zip(obj.columns, stored_columns))
        d_column_map = dict(column_map)
        dtypes = {
            d_column_map.get(k): v.name
            for k, v in obj.dtypes.items()
        }
        kind_meta = {
            'columns': column_map,
            'dtypes': dtypes,
            'idx_meta': idx_meta
        }
        # ensure column names to be strings
        obj.columns = stored_columns
        # create mongon indicies for data frame index columns
        df_idxcols = [col for col in obj.columns if col.startswith('_idx#')]
        if df_idxcols:
            keys, idx_kwargs = MongoQueryOps().make_index(df_idxcols)
            ensure_index(collection, keys, **idx_kwargs)
        # create index on row id
        keys, idx_kwargs = MongoQueryOps().make_index(['_om#rowid'])
        ensure_index(collection, keys, **idx_kwargs)
        # bulk insert
        # -- get native objects
        # -- seems to be required since pymongo 3.3.x. if not converted
        #    pymongo raises Cannot Encode object for int64 types
        if ensure_compat:
            for col, col_dtype in dtypes.items():
                if 'datetime' in col_dtype:
                    obj[col].fillna('', inplace=True)
        obj = obj.astype('O', errors='ignore')
        _fast_insert(obj, self, name, chunksize=chunksize)
        kind = (MDREGISTRY.PANDAS_SEROWS
                if store_series
                else MDREGISTRY.PANDAS_DFROWS)
        meta = self.store._make_metadata(name=name,
                                         prefix=self.store.prefix,
                                         bucket=self.store.bucket,
                                         kind=kind,
                                         kind_meta=kind_meta,
                                         attributes=attributes,
                                         collection=collection.name)
        return meta.save()

    def put_dataframe_as_dfgroup(self, obj, name, groupby, attributes=None):
        """
        store a dataframe grouped by columns in a mongo document

        :Example:

          > # each group
          >  {
          >     #group keys
          >     key: val,
          >     _data: [
          >      # only data keys
          >        { key: val, ... }
          >     ]}

        """

        def row_to_doc(obj):
            for gval, gdf in obj.groupby(groupby):
                if hasattr(gval, 'astype'):
                    gval = make_tuple(gval.astype('O'))
                else:
                    gval = make_tuple(gval)
                doc = dict(zip(groupby, gval))
                datacols = list(set(gdf.columns) - set(groupby))
                doc['_data'] = gdf[datacols].astype('O').to_dict('records')
                yield doc

        datastore = self.collection(name)
        datastore.drop()
        datastore.insert_many(row_to_doc(obj))
        return self.store._make_metadata(name=name,
                                         prefix=self.store.prefix,
                                         bucket=self.store.bucket,
                                         kind=MDREGISTRY.PANDAS_DFGROUP,
                                         attributes=attributes,
                                         collection=datastore.name).save()

    def put_dataframe_as_hdf(self, obj, name, attributes=None, **kwargs):
        filename = self.store.object_store_key(name, '.hdf')
        hdffname = self._package_dataframe2hdf(obj, filename)
        with open(hdffname, 'rb') as fhdf:
            fileid = self.store.fs.put(fhdf, filename=filename)
        return self.store._make_metadata(name=name,
                                         prefix=self.store.prefix,
                                         bucket=self.store.bucket,
                                         kind=MDREGISTRY.PANDAS_HDF,
                                         attributes=attributes,
                                         gridfile=GridFSProxy(db_alias=self.store._dbalias,
                                                              grid_id=fileid)).save()

    def put_ndarray_as_hdf(self, obj, name, attributes=None, **kwargs):
        """ store numpy array as hdf

        this is hack, converting the array to a dataframe then storing
        it
        """
        import pandas as pd
        df = pd.DataFrame(obj)
        return self.put_dataframe_as_hdf(df, name, attributes=attributes)

    def put_pyobj_as_hdf(self, obj, name, attributes=None, **kwargs):
        """
        store list, tuple, dict as hdf

        this requires the list, tuple or dict to be convertible into
        a dataframe
        """
        import pandas as pd
        df = pd.DataFrame(obj)
        return self.put_dataframe_as_hdf(df, name, attributes=attributes)

    def put_pyobj_as_document(self, obj, name, attributes=None, append=True, index=None, as_many=None, **kwargs):
        """
        store a dict as a document

        similar to put_dataframe_as_documents no data will be replaced by
        default. that is, obj is appended as new documents into the objects'
        mongo collection. to replace the data, specify append=False.
        """
        collection = self.collection(name)
        if append is False:
            collection.drop()
        elif append is None and collection.esimated_document_count(limit=1):
            from warnings import warn
            warn('%s already exists, will append rows' % name)
        if index:
            # create index with appropriate options
            from omegaml.store import MongoQueryOps
            if isinstance(index, dict):
                idx_kwargs = index
                index = index.pop('columns')
            else:
                idx_kwargs = {}
            index = [f'data.{c}' for c in index]
            keys, idx_kwargs = MongoQueryOps().make_index(index, **idx_kwargs)
            ensure_index(collection, keys, **idx_kwargs)
        if as_many is None:
            as_many = isinstance(obj, (list, tuple)) and isinstance(obj[0], (list, tuple))
        if as_many:
            # list of lists are inserted as many objects, as in pymongo < 4
            records = (mongo_compatible({'data': item}) for item in obj)
            result = collection.insert_many(records)
            objid = result.inserted_ids[-1]
        else:
            result = collection.insert_one(mongo_compatible({'data': obj}))
            objid = result.inserted_id

        return self.store._make_metadata(name=name,
                                         prefix=self.store.prefix,
                                         bucket=self.store.bucket,
                                         kind=MDREGISTRY.PYTHON_DATA,
                                         collection=collection.name,
                                         attributes=attributes,
                                         objid=objid).save()

    def get_dataframe_documents(self, name, columns=None, lazy=False,
                                filter=None, version=-1, is_series=False,
                                chunksize=None, sanitize=True, trusted=None,
                                **kwargs):
        """
        Internal method to return DataFrame from documents

        :param name: the name of the object (str)
        :param columns: the column projection as a list of column names
        :param lazy: if True returns a lazy representation as an MDataFrame.
           If False retrieves all data and returns a DataFrame (default)
        :param filter: the filter to be applied as a column__op=value dict
        :param sanitize: sanitize filter by removing all $op filter keys,
          defaults to True. Specify False to allow $op filter keys. $where
          is always removed as it is considered unsafe.
        :param version: the version to retrieve (not supported)
        :param is_series: if True retruns a Series instead of a DataFrame
        :param kwargs: remaining kwargs are used a filter. The filter kwarg
           overrides other kwargs.
        :return: the retrieved object (DataFrame, Series or MDataFrame)

        """
        from omegaml.store.queryops import sanitize_filter
        from omegaml.store.filtered import FilteredCollection

        collection = self.collection(name)
        meta = self.store.metadata(name)
        filter = filter or kwargs
        filter = sanitize_filter(filter, no_ops=sanitize, trusted=trusted)
        if lazy or chunksize:
            from ..mdataframe import MDataFrame
            df = MDataFrame(collection,
                            metadata=meta.kind_meta,
                            columns=columns).query(**filter)
            if is_series:
                df = df[0]
            if chunksize is not None and chunksize > 0:
                return df.iterchunks(chunksize=chunksize)
        else:
            # TODO ensure the same processing is applied in MDataFrame
            # TODO this method should always use a MDataFrame disregarding lazy
            if filter:
                query = Filter(collection, **filter).query
                cursor = FilteredCollection(collection).find(filter=query, projection=columns)
            else:
                cursor = FilteredCollection(collection).find(projection=columns)
            # restore dataframe
            df = cursor_to_dataframe(cursor)
            if '_id' in df.columns:
                del df['_id']
            if hasattr(meta, 'kind_meta'):
                df = convert_dtypes(df, meta.kind_meta.get('dtypes', {}))
            # -- restore columns
            meta_columns = dict(meta.kind_meta.get('columns'))
            if meta_columns:
                # apply projection, if any
                if columns:
                    # get only projected columns
                    # meta_columns is {origin_column: stored_column}
                    orig_columns = dict({k: v for k, v in meta_columns.items()
                                         if k in columns or v in columns})
                else:
                    # restore columns to original name
                    orig_columns = meta_columns
                df.rename(columns=orig_columns, inplace=True)
            # -- restore indexes
            idx_meta = meta.kind_meta.get('idx_meta')
            if idx_meta:
                df = restore_index(df, idx_meta)
            # -- restore row order
            if is_series:
                index = df.index
                name = df.columns[0]
                df = df[name]
                df.index = index
                df.name = None if name == 'None' else name
        return df

    def rebuild_params(self, kwargs, collection):
        """
        Returns a modified set of parameters for querying mongodb
        based on how the mongo document is structured and the
        fields the document is grouped by.

        **Note: Explicitly to be used with get_grouped_data only**

        :param kwargs: Mongo filter arguments
        :param collection: The name of mongodb collection
        :return: Returns a set of parameters as dictionary.
        """
        modified_params = {}
        db_structure = collection.find_one({}, {'_id': False})
        groupby_columns = list(set(db_structure.keys()) - set(['_data']))
        if kwargs is not None:
            for item in kwargs:
                if item not in groupby_columns:
                    modified_query_param = '_data.' + item
                    modified_params[modified_query_param] = kwargs.get(item)
                else:
                    modified_params[item] = kwargs.get(item)
        return modified_params

    def get_dataframe_dfgroup(self, name, version=-1, sanitize=True, lazy=False, **kwargs):
        """
        Return a grouped dataframe

        :param name: the name of the object
        :param version: not supported
        :param kwargs: mongo db query arguments to be passed to
               collection.find() as a filter.
        :param sanitize: remove any $op operators in kwargs

        .. versionchanged:: NEXT
            filters are now specified as **kwargs, not kwargs= (still supported for backwards compatibility)

        """
        import pandas as pd
        from omegaml.store.queryops import sanitize_filter
        from omegaml.store.filtered import FilteredCollection

        def convert_doc_to_row(cursor):
            for doc in cursor:
                data = doc.pop('_data', [])
                for row in data:
                    doc.update(row)
                    yield doc

        datastore = FilteredCollection(self.collection(name))
        kwargs = kwargs.get('kwargs', kwargs)  # support backwards-compatible kwargs=
        params = self.rebuild_params(kwargs, datastore)
        if lazy:
            return FilteredCollection(datastore, query=params)
        params = sanitize_filter(params, no_ops=sanitize)
        cursor = datastore.find(params, projection={'_id': False})
        df = pd.DataFrame(convert_doc_to_row(cursor))
        return df

    def get_dataframe_hdf(self, name, version=-1):
        """
        Retrieve dataframe from hdf

        :param name: The name of object
        :param version: The version of object (not supported)
        :return: Returns a python pandas dataframe
        :raises: gridfs.errors.NoFile
        """
        df = None
        meta = self.store.metadata(name)
        filename = getattr(meta.gridfile, 'name', self.store.object_store_key(name, '.hdf'))
        if self.store.fs.exists(filename=filename):
            df = self._extract_dataframe_hdf(filename, version=version)
            return df
        else:
            raise gridfs.errors.NoFile(
                "{0} does not exist in mongo collection '{1}'".format(
                    name, self.store.bucket))

    def get_python_data(self, name, filter=None, version=-1, lazy=False, trusted=False, **kwargs):
        """
        Retrieve objects as python data

        :param name: The name of object
        :param version: The version of object

        :return: Returns the object as python list object
        """
        datastore = self.collection(name)
        filter = filter or kwargs
        sanitize_filter(filter) if trusted is False or trusted != signature(filter) else filter
        cursor = datastore.find(filter, **kwargs)
        if lazy:
            return cursor
        data = (d.get('data') for d in cursor)
        return list(data)

    def get_object_as_python(self, meta, version=-1):
        """
        Retrieve object as python object

        :param meta: The metadata object
        :param version: The version of the object

        :return: Returns data as python object
        """
        if meta.kind == MDREGISTRY.SKLEARN_JOBLIB:
            return meta.gridfile
        if meta.kind == MDREGISTRY.PANDAS_HDF:
            return meta.gridfile
        if meta.kind == MDREGISTRY.PANDAS_DFROWS:
            return list(getattr(self.store.mongodb, meta.collection).find())
        if meta.kind == MDREGISTRY.PYTHON_DATA:
            col = getattr(self.store.mongodb, meta.collection)
            return col.find_one(dict(_id=meta.objid)).get('data')
        raise TypeError('cannot return kind %s as a python object' % meta.kind)

    def _package_dataframe2hdf(self, df, filename, key=None):
        """
        Package a dataframe as a hdf file

        :param df: The dataframe
        :param filename: Name of file

        :return: Filename of hdf file
        """
        lpath = tempfile.mkdtemp()
        fname = os.path.basename(filename)
        hdffname = os.path.join(self.store.tmppath, fname + '.hdf')
        key = key or 'data'
        df.to_hdf(hdffname, key)
        return hdffname

    def _extract_dataframe_hdf(self, filename, version=-1):
        """
        Extracts a dataframe from a stored hdf file

        :param filename: The name of file
        :param version: The version of file

        :return: Pandas dataframe
        """
        import pandas as pd
        hdffname = os.path.join(self.store.tmppath, filename)
        dirname = os.path.dirname(hdffname)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        try:
            outf = self.store.fs.get_version(filename, version=version)
        except gridfs.errors.NoFile as e:
            raise e
        with open(hdffname, 'wb') as hdff:
            hdff.write(outf.read())
        hdf = pd.HDFStore(hdffname)
        key = list(hdf.keys())[0]
        df = hdf[key]
        hdf.close()
        return df
