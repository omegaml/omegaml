from __future__ import absolute_import

import os

from warnings import warn

from dataset.table import Table
from dataset_orm import connect, files

from omegaml.models import Metadata


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
            self._db = connect('sqlite:///db.sqlite')
            # make compatible to mongodb store
            # -- table semantics
            Table.insert_one = Table.insert
            # -- shim for filelike()
            files.FileLike.get = lambda self: self
            # -- delete, remove
            files.FileLike.delete = files.FileLike.remove
        return DatabaseShim(self._db)

    def _get_Metadata(self):
        return Metadata

    def _get_filesystem(self):
        """
        Retrieve a gridfs instance using url and collection provided

        :return: a gridfs instance
        """
        return files

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
            datastore = TableCollection(self.db[collection])
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
        search = {}
        pattern = pattern or '*'
        if pattern:
            search['pattern__like'] = pattern
        if bucket:
            search['bucket'] = bucket
        if prefix:
            search['prefix'] = prefix
        items = self._Metadata.objects.find(**search)
        if raw:
            items = items.as_list()
        else:
            items = [item.name for item in items]
        return items


class TableCollection:
    def __init__(self, table):
        self.table = table

    def __getattr__(self, k):
        return getattr(self.table, k)

    def count_documents(self, *args, **kwargs):
        return self.table.count()

    def estimated_document_count(self):
        return self.count_documents()

    def list_indexes(self):
        return self.table._indexes


class DatabaseShim:
    def __init__(self, db):
        self.db = db

    def __getattr__(self, k):
        return getattr(self.db, k)

    def __getitem__(self, item):
        return self.db[item]

    def drop_collection(self, name):
        if name in self.db.tables:
            self.db[name].drop()


