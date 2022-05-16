from __future__ import absolute_import

import bson
import gridfs
import os
from mongoengine import GridFSProxy, Q
from mongoengine.connection import disconnect, \
    connect, _connections, get_db
from uuid import uuid4
from warnings import warn

from omegaml.store.documents import make_Metadata
from omegaml.mongoshim import sanitize_mongo_kwargs, waitForConnection
from omegaml.store.fastinsert import fast_insert, default_chunksize
from omegaml.util import (urlparse, ensure_index, PickableCollection)


class MongoStoreMixin:
    @classmethod
    def supports(cls, obj, prefix=None, **kwargs):
        return True  # support all types of storage

    def _get_database(self):
        """
        Returns a mongo database object
        """
        if self._db is not None:
            return self._db
        # parse salient parts of mongourl, e.g.
        # mongodb://user:password@host/dbname
        self.parsed_url = urlparse.urlparse(self.mongo_url)
        self.database_name = self.parsed_url.path[1:]
        host = self.parsed_url.netloc
        scheme = self.parsed_url.scheme
        username, password = None, None
        if '@' in host:
            creds, host = host.split('@', 1)
            if ':' in creds:
                username, password = creds.split(':')
        # connect via mongoengine
        #
        # note this uses a MongoClient in the background, with pooled
        # connections. there are multiprocessing issues with pymongo:
        # http://api.mongodb.org/python/3.2/faq.html#using-pymongo-with-multiprocessing
        # connect=False is due to https://jira.mongodb.org/browse/PYTHON-961
        # this defers connecting until the first access
        # serverSelectionTimeoutMS=2500 is to fail fast, the default is 30000
        #
        # use an instance specific alias, note that access to Metadata and
        # QueryCache must pass the very same alias
        self._dbalias = alias = self._dbalias or 'omega-{}'.format(uuid4().hex)
        # always disconnect before registering a new connection because
        # mongoengine.connect() forgets all connection settings upon disconnect
        if alias not in _connections:
            disconnect(alias)
            connection = connect(alias=alias, db=self.database_name,
                                 host=f'{scheme}://{host}',
                                 username=username,
                                 password=password,
                                 connect=False,
                                 authentication_source='admin',
                                 serverSelectionTimeoutMS=self.defaults.OMEGA_MONGO_TIMEOUT,
                                 **sanitize_mongo_kwargs(self.defaults.OMEGA_MONGO_SSL_KWARGS),
                                 )
            # since PyMongo 4, connect() no longer waits for connection
            waitForConnection(connection)
        self._db = get_db(alias)
        return self._db

    def _get_Metadata(self):
        return  make_Metadata(db_alias=self._dbalias,
                              collection=self._fs_collection)

    def _get_filesystem(self):
        """
        Retrieve a gridfs instance using url and collection provided

        :return: a gridfs instance
        """
        if self._fs is None:
            self._fs = GridFSShim(self, self.db, collection=self._fs_collection)
        return self._fs

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
            datastore = getattr(self.db, collection)
        except Exception as e:
            raise e
        return PickableCollection(datastore)

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
            for fileobj in self.fs.find({'filename': filename}):
                try:
                    self.fs.delete(fileobj._id)
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

        regex = lambda pattern: bson.regex.Regex(f'{pattern}')
        db = self.db
        searchkeys = dict(bucket=bucket or self.bucket,
                          prefix=prefix or self.prefix)
        q_excludes = Q()
        if regexp:
            searchkeys['name'] = regex(regexp)
        elif pattern:
            re_pattern = pattern.replace('*', '.*').replace('/', '\/')
            searchkeys['name'] = regex(f'^{re_pattern}$')
        if not include_temp:
            q_excludes &= Q(name__not__startswith='_')
            q_excludes &= Q(name__not=regex(r'(.{1,*}\/?_.*)'))
        if not hidden:
            q_excludes &= Q(name__not__startswith='.')
        if kind or self.force_kind:
            kind = kind or self.force_kind
            if isinstance(kind, (tuple, list)):
                searchkeys.update(kind__in=kind)
            else:
                searchkeys.update(kind=kind)
        if filter:
            searchkeys.update(filter)
        q_search = Q(**searchkeys) & q_excludes
        files = self._Metadata.objects.no_cache()(q_search)
        return [f if raw else str(f.name).replace('.omm', '') for f in files]

    def _find_metadata(self, name=None, bucket=None, prefix=None, version=-1, **kwargs):
        """
        Returns a metadata document for the given entry name
        """
        # FIXME: version attribute does not do anything
        # FIXME: metadata should be stored in a bucket-specific collection
        # to enable access control, see https://docs.mongodb.com/manual/reference/method/db.create
        #
        # Role/#db.createRole
        db = self.mongodb
        fs = self.fs
        prefix = prefix or self.prefix
        bucket = bucket or self.bucket
        # Meta is to silence lint on import error
        Meta = self._Metadata
        return Meta.objects(name=str(name), prefix=prefix, bucket=bucket).no_cache().first()

    def _fast_insert(df, store, name, chunksize=default_chunksize):
        fast_insert(df, store, name, chunksize=chunksize)


class GridFSShim(gridfs.GridFS):
    def __init__(self, store, database, collection='fs'):
        super().__init__(database, collection=collection)
        self._omstore = store
        self._ensure_fs_collection()
        self._ensure_fs_index(self)

    def put(self, *args, **kwargs):
        # return a filelike instead of a fileid
        gridid = super().put(*args, **kwargs)
        filelike = GridFSProxy(db_alias=self._omstore._dbalias,
                               grid_id=gridid)
        return filelike

    def _ensure_fs_collection(self):
        # ensure backwards-compatible gridfs access
        if self._omstore.OMEGA_BUCKET_FS_LEGACY:
            # prior to 0.13.2 a single gridfs instance was used, always equal to the default collection
            return self._omstore.defaults.OMEGA_MONGO_COLLECTION
        if self._omstore.bucket == self._omstore.defaults.OMEGA_MONGO_COLLECTION:
            # from 0.13.2 onwards, only the default bucket is equal to the default collection
            # backwards compatibility for existing installations
            return self._omstore.bucket
        # since 0.13.2, all buckets other than the default use a qualified collection name to
        # effectively separate files in different buckets, enabling finer-grade access control
        # and avoiding name collisions from different buckets
        return '{}_{}'.format(self._omstore.defaults.OMEGA_MONGO_COLLECTION, self._omstore.bucket)

    def _ensure_fs_index(self, fs):
        # make sure we have proper chunks and file indicies. this should be created on first write, but sometimes is not
        # see https://docs.mongodb.com/manual/core/gridfs/#gridfs-indexes
        ensure_index(fs._GridFS__chunks, {'files_id': 1, 'n': 1}, unique=True)
        ensure_index(fs._GridFS__files, {'filename': 1, 'uploadDate': 1})
