from __future__ import absolute_import

import gridfs
from mongoengine.connection import disconnect, \
    connect, _connections, get_db
from uuid import uuid4

from omegaml.documents import make_Metadata
from omegaml.mongoshim import sanitize_mongo_kwargs, waitForConnection
from omegaml.util import (urlparse, ensure_index)


class MongoStoreMixin:
    def _init_mixin(self, *args, **kwargs):
        self._fs_collection = self._ensure_fs_collection()

    @classmethod
    def supports(cls, obj, prefix=None, **kwargs):
        return True # support all types of storage

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
        if self._Metadata_cls is None:
            # hack to localize metadata
            db = self.db
            self._Metadata_cls = make_Metadata(db_alias=self._dbalias,
                                               collection=self._fs_collection)
        return self._Metadata_cls

    def _get_filesystem(self):
        """
        Retrieve a gridfs instance using url and collection provided

        :return: a gridfs instance
        """
        if self._fs is not None:
            return self._fs
        self._fs = gridfs.GridFS(self.db, collection=self._fs_collection)
        self._ensure_fs_index(self._fs)
        return self._fs

    def _ensure_fs_collection(self):
        # ensure backwards-compatible gridfs access
        if self.defaults.OMEGA_BUCKET_FS_LEGACY:
            # prior to 0.13.2 a single gridfs instance was used, always equal to the default collection
            return self.defaults.OMEGA_MONGO_COLLECTION
        if self.bucket == self.defaults.OMEGA_MONGO_COLLECTION:
            # from 0.13.2 onwards, only the default bucket is equal to the default collection
            # backwards compatibility for existing installations
            return self.bucket
        # since 0.13.2, all buckets other than the default use a qualified collection name to
        # effectively separate files in different buckets, enabling finer-grade access control
        # and avoiding name collisions from different buckets
        return '{}_{}'.format(self.defaults.OMEGA_MONGO_COLLECTION, self.bucket)

    def _ensure_fs_index(self, fs):
        # make sure we have proper chunks and file indicies. this should be created on first write, but sometimes is not
        # see https://docs.mongodb.com/manual/core/gridfs/#gridfs-indexes
        ensure_index(fs._GridFS__chunks, {'files_id': 1, 'n': 1}, unique=True)
        ensure_index(fs._GridFS__files, {'filename': 1, 'uploadDate': 1})
