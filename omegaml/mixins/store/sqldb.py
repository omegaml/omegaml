from __future__ import absolute_import

import os
from dataset.table import Table
from dataset.types import Types
from dataset_orm import connect, files
from functools import lru_cache
from warnings import warn

from omegaml.store.models import Metadata


class DatasetStoreMixin:
    def _init_mixin(self, *args, **kwargs):
        pass

    @classmethod
    def supports(cls, obj, prefix=None, **kwargs):
        return True  # support all types of storage

    def _get_database(self):
        """
        Returns a mongo database object
        """
        if self._db is None:
            dbname = self.mongo_url.split('/')[-1]
            db = sqlconnect(f'sqlite:////tmp/{dbname}.sqlite', alias=self._dbalias)
            self._db = DatabaseShim(db)
            # make compatible to mongodb store
            # -- table semantics
            Table.insert_one = Table.insert
            # Table.database = property(lambda self: DatabaseShim(self.db))
            # -- shim for filelike()
            files.FileLike.get = lambda self: self
            # -- delete, remove
            files.FileLike.delete = files.FileLike.remove
        return self._db

    def _get_Metadata(self):
        return Metadata._make_using(self.db.db)

    def _get_filesystem(self):
        """
        Retrieve a gridfs instance using url and collection provided

        :return: a gridfs instance
        """
        db = self.db
        with files.using(self._dbalias) as files_as:
            return files_as

    def _find_metadata(self, name=None, bucket=None, prefix=None, **kwargs):
        # FIXME: version attribute does not do anything
        # FIXME: metadata should be stored in a bucket-specific collection
        # to enable access control, see https://docs.mongodb.com/manual/reference/method/db.create
        #
        # Role/#db.createRole
        db = self.db
        fs = self.fs
        prefix = prefix or self.prefix
        bucket = bucket or self.bucket
        # Meta is to silence lint on import error
        Meta = self._Metadata
        return Meta.objects.find(name=str(name), prefix=prefix, bucket=bucket).nocache().first()

    def _get_collection(self, name=None, bucket=None, prefix=None):
        """
        Returns a mongo db collection as a datastore

        If there is an existing object of name, will return the .collection
        of the object. Otherwise returns the collection according to naming
        convention {bucket}.{prefix}.{name}.datastore

        :param name: the collection to use. if none defaults to the
            collection name given on instantiation. the actual collection name
            used is always prefix + name + '.data'
        """
        # see if we have a known object and a collection for that, if not define it
        meta = self.metadata(name, bucket=bucket, prefix=prefix)
        collection = meta.collection if meta else None
        if not collection:
            collection = self.object_store_key(name, '.datastore')
            collection = collection.replace('..', '.')
        # return the collection
        try:
            datastore = self.db[collection]
        except Exception as e:
            raise e
        return datastore

    def _save_file(self, obj, filename, encoding=None, replace=False):
        """
        Use this method to store file-like objects to the store's gridfs

        Args:
            store (OmegaStore): the store whose .fs filesystem access will be used
            obj (file-like): a file-like object or path, if path will be opened with mode=rb,
               otherwise its obj.read() method is called to get the data as a byte stream
            filename (path): the path in the store (key)
            encoding (str): a valid encoding such as utf8, optional
            replace (bool): if True the existing file(s) of the same name are deleted to avoid automated versioning
               by gridfs. defaults to False

        Returns:
            gridfile (GridFSProxy), assignable to Metadata.gridfile
        """
        if replace:
            for fileobj in self.fs.find(filename=filename):
                try:
                    self.fs.remove(filename)
                except Exception as e:
                    warn('deleting {filename} resulted in {e}'.format(**locals()))
                    pass
        if os.path.exists(str(obj)):
            with open(obj, 'rb') as fin:
                filelike = self.fs.put(fin, filename=filename)
        else:
            filelike = self.fs.put(obj, filename=filename)
        return filelike

    def _get_list(self, pattern=None, regexp=None, kind=None, raw=False, hidden=None,
                  include_temp=False, bucket=None, prefix=None, filter=None):
        db = self.db
        searchkeys = dict(bucket=bucket or self.bucket,
                          prefix=prefix or self.prefix)
        pattern = pattern or '*'
        if pattern:
            searchkeys['name__like'] = pattern.replace('*', '%')
        if regexp:
            searchkeys['name__regexp'] = regexp
        if bucket:
            searchkeys['bucket'] = bucket
        if prefix:
            searchkeys['prefix'] = prefix
        if kind:
            searchkeys['kind'] = kind
        items = self._Metadata.objects.find(**searchkeys, order_by=['name'])
        should_include = lambda v: (not (v.startswith('.') or v.startswith('_')) or
                                    (v.startswith('.') and hidden) or
                                    (v.startswith('_') and include_temp))
        if raw:
            items = [item for item in items if should_include(item.name)]
        else:
            items = [item.name for item in items if should_include(item.name)]
        return items

    def _fast_insert(self, df, store, name, chunksize=None):
        store.collection(name).insert_many(df.to_dict(orient='records'), chunk_size=chunksize)


class TableCollection:
    # shim a dataset.Table to duck as a pymongo.Collection
    def __init__(self, table, limit=None, offset=0):
        self.table = table

    def __getattr__(self, k):
        return getattr(self.table, k)

    def with_options(self, *args, **kwargs):
        # not supported by sqla
        return self

    def count_documents(self, *args, **kwargs):
        return self.table.count()

    def estimated_document_count(self):
        return self.count_documents()

    def list_indexes(self):
        return [specs for idx, specs in self.index_information().items()]

    def find(self, filter=None, projection=None, **kwargs):
        kwargs.update(filter) if filter else None
        result = DeferredCursor(self.table, filter=kwargs, projection=projection)
        return result

    def find_one(self, filter=None, projection=None, **kwargs):
        kwargs.update(filter) if filter else None
        result = list(DeferredCursor(self.table, filter=kwargs, projection=projection, limit=1))
        return result[0] if len(result) else None

    def replace_one(self, flt, data):
        data.update(flt)
        keys = list(flt.keys())
        keys = list(set(['id'] + keys))  # always include the id column
        return self.table.update(data, keys)

    def distinct(self, key, filter=None, **kwargs):
        filter = filter or {}
        return (row[key] for row in self.table.distinct(key, **filter))

    def create_index(self, columns, name=None, **kwargs):
        columns = list(dict(columns))
        name = name or '_'.join(columns)
        name = f'{self.table.name}_{name}'
        self.table.create_index(columns, name=name, **kwargs)

    def index_information(self):
        # transform index information into mongo-like format
        # - get_indexes() returns a list of dicts
        #   {name=>str, column_names=>[], unique=>bool, column_sorting={}}
        # - returns a dict
        #   {name=>{unique=>bool, key=>[(column, sortord)]}
        indexes = self.table.db.inspect.get_indexes(self.name, schema=self.db.schema)
        sortord = lambda v: -1 if v == 'desc' else 1
        indexes = {
            idx['name']: {
                'unique': idx.get('unique', False),
                'key': [(c, sortord(idx.get('column_sorting', {}).get(c)))
                        for c in idx['column_names']]
            }
            for idx in indexes
        }
        return indexes


class DeferredCursor:
    # a cursor that is only evaluated on starting the iteration
    # before it is started can set head(), limit(), sort()
    def __init__(self, table, filter=None, projection=None, limit=None):
        self.table = table
        self._filter = filter
        self._projection = projection
        self._limit = limit
        self._offset = 0
        self._sort_order = None

    def limit(self, n):
        self._limit = n

    def skip(self, n):
        self._offset = n

    def sort(self, columns):
        self._sort_order = [('-' if order < 0 else '') + f'{col}'
                            for col, order in columns]

    def _sqlize(self, filter):
        # transform mongodb filter spec into dataset-lib advanced filter spec
        # example:
        # {'$and': [{'_om#rowid': {'$gte': 2}}, {'_om#rowid': {'$lte': 3}}]}
        # => { '_om#rowid': { 'gte': 2 }}
        ensure_list = lambda v: [v] if not isinstance(v, (list, set, tuple)) else v
        for k, v in filter.items():
            if isinstance(v, dict):
                filter[k] = self._sqlize(v)
        if '$and' in filter:
            # some and'ed conditions
            clauses = filter.get('$and')
            transform = True
        elif any(k.startswith('$') for k in filter):
            # some $operator
            clauses = ensure_list(filter)
            transform = True
        elif any('.' in k for k in filter):
            transform = True
            clauses = ensure_list(filter)
        else:
            # no mongodb filter found, process as is
            transform = False
            clauses = None
        if transform:
            column_clauses = {}
            sqlop = lambda v: v.replace('$', '')  # $eq => eq
            colq = lambda v: v.split('.')[-1]  # data.experiment => experiment
            for clause in clauses:
                for op, spec in clause.items():
                    column_clauses[colq(sqlop(op))] = spec
            filter = column_clauses
        return filter

    def __iter__(self):
        for item in self.table.find(**self._sqlize(self._filter),
                                    _limit=self._limit,
                                    _offset=self._offset,
                                    order_by=self._sort_order):
            if self._projection:
                item = {k: v for k, v in item.items() if k in self._projection}
            yield item


class DatabaseShim:
    # shim a dataset.Database to duck as pymongo.Database
    def __init__(self, db):
        self.db = db
        self.db.types = ExtendedTypes(is_postgres=db.is_postgres)

    def __getattr__(self, k):
        return getattr(self.db, k)

    def __getitem__(self, item):
        return TableCollection(self.db.get_table(item, primary_id='_id'))

    def drop_collection(self, name):
        if name in self.db.tables:
            table = self[name]
            table.drop()

    def list_collection_names(self):
        return self.db.tables

    def command(self, *args, **kwargs):
        # not supported by sqla
        pass


class ExtendedTypes(Types):
    # Types override to accept lists as json
    # -- makes native python objects work
    # -- remove when done in upstream dataset https://github.com/pudo/dataset/pull/392
    def guess(self, sample):
        if isinstance(sample, list):
            return self.json
        return super().guess(sample)

@lru_cache()
def sqlconnect(url=None, alias=None, recreate=False, **kwargs):
    # we cache this so we get the same connection for the same alias
    # this ensures tests work across threads
    return connect(url=url, recreate=recreate, alias=alias, **kwargs)
