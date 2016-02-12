from fnmatch import fnmatch
import glob
import os
import re
from shutil import rmtree
import tempfile
import urlparse
from zipfile import ZipFile, ZIP_DEFLATED

import gridfs
import joblib
from pymongo.mongo_client import MongoClient
from sklearn.base import BaseEstimator
from sklearn.pipeline import Pipeline

from omega import defaults
import pandas as pd


class OmegaStore(object):

    def __init__(self, mongo_url=None, bucket=None, prefix=None):
        """
        :param mongo_url: the mongourl to use for the gridfs
        :param bucket: the mongo collection to use for gridfs
        :param prefix: the path prefix for files. defaults to blank 
        """
        self.mongo_url = mongo_url or defaults.OMEGA_MONGO_URL
        self.bucket = bucket or defaults.OMEGA_MONGO_COLLECTION
        self._fs = None
        self.tmppath = defaults.OMEGA_TMP
        self.prefix = prefix or ''

    @property
    def fs(self):
        """
        get gridfs instance using url and collection provided
        """
        if self._fs is not None:
            return self._fs
        self.parsed_url = urlparse.urlparse(self.mongo_url)
        self.database_name = self.parsed_url.path[1:]
        try:
            db = getattr(MongoClient(self.mongo_url), self.database_name)
            self._fs = gridfs.GridFS(db, collection=self.bucket)
        except Exception as e:
            raise e
        return self._fs

    def datastore(self, name=None):
        """
        return a mongo db collection as a datastore

        :param name: the collection to use. if none defaults to the
        collection name given on instantiation. the actual collection name
        used is always prefix + name + '.data'
        """
        self.parsed_url = urlparse.urlparse(self.mongo_url)
        self.database_name = self.parsed_url.path[1:]
        collection_name = '%s%s.%s' % (self.prefix, self.bucket, name)
        try:
            db = getattr(MongoClient(self.mongo_url), self.database_name)
            collection = collection_name + '.data'
            datastore = getattr(db, collection)
        except Exception as e:
            raise e
        return datastore

    def put(self, obj, name, meta=None):
        """ store an object

        store estimators, pipelines, numpy arrays or pandas dataframes
        """
        if isinstance(obj, (BaseEstimator, Pipeline)):
            self.put_model(obj, name, meta)
        elif isinstance(obj, pd.DataFrame):
            self.put_dataframe_as_documents(obj, name, meta)

    def put_model(self, obj, name, meta=None):
        """ package model using joblib and store in GridFS """ 
        zipfname = self._package_model(obj, name)
        with open(zipfname) as fzip:
            fileid = self.fs.put(
                fzip, filename=self.prefix + name + '.omm')
        return fileid

    def put_dataframe_as_documents(self, obj, name, meta=None):
        """ store a dataframe as a row-wise collection of documents """ 
        datastore = self.datastore(name)
        datastore.drop()
        datastore.insert_many((row[1].to_dict() for row in obj.iterrows()))

    def get(self, name, version=-1):
        """
        retrieve an object

        retrieve estimators, pipelines, data array or pandas dataframe
        previously stored with put()
        """
        # see if it's a modelfile
        filename = self.prefix + name + \
            '.omm' if not name.endswith('.omm') else name
        if filename.endswith('.omm') and self.fs.exists(filename=filename):
            packagefname = os.path.join(self.tmppath, filename)
            dirname = os.path.dirname(packagefname)
            try:
                os.makedirs(dirname)
            except OSError:
                # OSError is raised if path exists already
                pass
            outf = self.fs.get_version(filename, version=version)
            with open(packagefname, 'w') as zipf:
                zipf.write(outf.read())
            model = self._extract_model(packagefname)
            return model
        else:
            # not a file, must be data then
            datastore = self.datastore(name)
            cursor = datastore.find()
            df = pd.DataFrame(list(cursor))
            if '_id' in df.columns:
                del df['_id']
            return df

    def list(self, pattern=None, regexp=None, raw=False):
        """
        list all files in store

        specify pattern as a unix pattern (e.g. 'models/*', 
        or sepcify regexp)

        :param pattern: the unix file pattern or None for all
        :param regexp: the regexp. takes precedence over pattern
        :param raw: if True return files as stored in GridFS, otherwise
        return names as passed in by caller 
        """
        files = self.fs.list()
        if regexp:
            files = [f for f in files if re.match(regexp, f)]
        elif pattern:
            files = [f for f in files if fnmatch(f, pattern)]
        if not raw:
            files = [f.replace('.omm', '') for f in files]
        return files

    def _package_model(self, model, filename):
        """
        dump model using joblib and package all joblib files into zip 
        """
        lpath = tempfile.mkdtemp()
        fname = os.path.basename(filename)
        mklfname = os.path.join(lpath, fname)
        zipfname = os.path.join(self.tmppath, fname + '.omm')
        joblib.dump(model, mklfname)
        with ZipFile(zipfname, 'w', compression=ZIP_DEFLATED) as zipf:
            for part in glob.glob(os.path.join(lpath, '*')):
                zipf.write(part, os.path.basename(part))
        rmtree(lpath)
        return zipfname

    def _extract_model(self, packagefname):
        """
        load model using joblib from a zip file created with _package_model
        """
        lpath = tempfile.mkdtemp()
        fname = os.path.basename(packagefname).replace('.omm', '')
        mklfname = os.path.join(lpath, fname)
        with ZipFile(packagefname) as zipf:
            zipf.extractall(lpath)
        model = joblib.load(mklfname)
        rmtree(lpath)
        return model
