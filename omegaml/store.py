from fnmatch import fnmatch
import glob
import os
import re
from shutil import rmtree
import tempfile
import urlparse
from zipfile import ZipFile, ZIP_DEFLATED

import gridfs
import mongoengine
from mongoengine.fields import GridFSProxy

import omegaml
from omegaml.documents import Metadata
from omegaml.util import is_estimator, is_dataframe


class OmegaStore(object):

    """
    native storage for OmegaML using a mongodb as the storage layer

    An OmegaStore instance is a MongoDB database. It has at least the
    metadata collection which lists all objects stored in it. A metadata
    document refers to the following types of objects (metadata.kind):

    * pandas.dfrows - a Pandas DataFrame stored as a collection of rows
    * sklearn.joblib - a scikit learn estimator/pipline dumped using joblib.dump()
    * python.data - an arbitrary python dict, tuple, list stored as a document

    Note that storing Pandas and scikit learn objects requires the availability
    of the respective packages. If either can not be imported, the OmegaStore
    degrades to a python.data store only. It will still .list() and get() any
    object, however reverts to pure python objects. In this case it is up
    to the client to convert the data into an appropriat format for processing.

    Pandas and scikit-learn objects can only be stored if these packages are
    availables. put() raises a TypeError if you pass such objects and they
    cannot be loaded.   
    """

    def __init__(self, mongo_url=None, bucket=None, prefix=None):
        """
        :param mongo_url: the mongourl to use for the gridfs
        :param bucket: the mongo collection to use for gridfs
        :param prefix: the path prefix for files. defaults to blank 
        """
        defaults = omegaml.settings()
        self.mongo_url = mongo_url or defaults.OMEGA_MONGO_URL
        self.bucket = bucket or defaults.OMEGA_MONGO_COLLECTION
        self._fs = None
        self.tmppath = defaults.OMEGA_TMP
        self.prefix = prefix or ''
        self._db = None

    @property
    def mongodb(self):
        if self._db is not None:
            return self._db
        self.parsed_url = urlparse.urlparse(self.mongo_url)
        self.database_name = self.parsed_url.path[1:]
        self._db = getattr(mongoengine.connect(self.database_name,
                                               host=self.mongo_url,
                                               alias='omega'),
                           self.database_name)
        return self._db

    @property
    def fs(self):
        """
        get gridfs instance using url and collection provided
        """
        if self._fs is not None:
            return self._fs
        try:
            self._fs = gridfs.GridFS(self.mongodb, collection=self.bucket)
        except Exception as e:
            raise e
        return self._fs

    def metadata(self, name=None):
        """
        return metadata document(s) for the given entry name
        """
        # ensure initialization
        db = self.mongodb
        return Metadata.objects(name=name)

    def datastore(self, name=None):
        """
        return a mongo db collection as a datastore

        :param name: the collection to use. if none defaults to the
        collection name given on instantiation. the actual collection name
        used is always prefix + name + '.data'
        """
        collection_name = '%s%s' % (self.prefix, name)
        try:
            collection = collection_name + '.data'
            datastore = getattr(self.mongodb, collection)
        except Exception as e:
            raise e
        return datastore

    def put(self, obj, name, attributes=None, **kwargs):
        """ store an object

        store estimators, pipelines, numpy arrays or pandas dataframes
        """
        if is_estimator(obj):
            return self.put_model(obj, name, attributes)
        elif is_dataframe(obj):
            if kwargs.get('as_hdf', False):
                return self.put_dataframe_as_hdf(obj, name, attributes)
            return self.put_dataframe_as_documents(obj, name, attributes)
        elif isinstance(obj, (dict, list, tuple)):
            return self.put_pyobj_as_document(obj, name, attributes)
        else:
            raise TypeError('type %s not supported' % type(obj))

    def put_model(self, obj, name, attributes=None):
        """ package model using joblib and store in GridFS """
        zipfname = self._package_model(obj, name)
        with open(zipfname) as fzip:
            fileid = self.fs.put(
                fzip, filename=self.prefix + name + '.omm')
        return Metadata(name=self.prefix + name,
                        kind=Metadata.SKLEARN_JOBLIB,
                        attributes=attributes,
                        gridfile=GridFSProxy(grid_id=fileid)).save()

    def put_dataframe_as_documents(self, obj, name, attributes=None):
        """ store a dataframe as a row-wise collection of documents """
        datastore = self.datastore(name)
        datastore.drop()
        datastore.insert_many((row[1].to_dict() for row in obj.iterrows()))
        return Metadata(name=self.prefix + name,
                        kind=Metadata.PANDAS_DFROWS,
                        attributes=attributes,
                        collection=datastore.name).save()

    def put_dataframe_as_hdf(self, obj, name, attributes=None):
        hdffname = self._package_dataframe2hdf(obj, name)
        with open(hdffname) as fhdf:
            fileid = self.fs.put(fhdf, filename=self.prefix + name + '.hdf')
        return Metadata(name=self.prefix + name,
                        kind=Metadata.PANDAS_HDF,
                        attributes=attributes,
                        gridfile=GridFSProxy(grid_id=fileid)).save()

    def put_pyobj_as_document(self, obj, name, attributes=None):
        """ store a dict as a document """
        datastore = self.datastore(name)
        datastore.drop()
        objid = datastore.insert({'data': obj})
        return Metadata(name=self.prefix + name,
                        kind=Metadata.PYTHON_DATA,
                        collection=datastore.name,
                        attributes=attributes,
                        objid=objid).save()

    def meta_for(self, name, version=-1):
        db = self.mongodb
        try:
            meta = list(Metadata.objects(name=self.prefix + name))[version]
        except IndexError:
            meta = None
        return meta

    def drop(self, name, version=-1):
        meta = self.meta_for(name, version=version)
        if meta.collection:
            self.mongodb.drop_collection(meta.collection)
            meta.delete()
            return True
        if meta.gridfile is not None:
            meta.gridfile.delete()
            meta.delete()
            return True
        return False

    def get(self, name, version=-1, force_python=False):
        """
        retrieve an object

        retrieve estimators, pipelines, data array or pandas dataframe
        previously stored with put()
        """
        meta = self.meta_for(name, version=version)
        if meta is None:
            return None
        if not force_python:
            if meta.kind == Metadata.SKLEARN_JOBLIB:
                return self.get_model(name, version=version)
            elif meta.kind == Metadata.PANDAS_DFROWS:
                return self.get_dataframe(name, version=version)
            elif meta.kind == Metadata.PYTHON_DATA:
                return self.get_python_data(name, version=version)
            elif meta.kind == Metadata.PANDAS_HDF:
                return self.get_dataframe_hdf(name, version=version)
        return self.get_object_as_python(meta, version=version)

    def get_model(self, name, version=-1):
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

    def get_dataframe(self, name, version=-1):
        import pandas as pd
        datastore = self.datastore(name)
        cursor = datastore.find()
        df = pd.DataFrame(list(cursor))
        if '_id' in df.columns:
            del df['_id']
        return df

    def get_dataframe_hdf(self, name, version=-1):
        filename = self.prefix + name + \
            '.hdf' if not name.endswith('.hdf') else name
        if filename.endswith('.hdf') and self.fs.exists(filename=filename):
            df = self._extract_dataframe_hdf(filename, version=version)
        return df

    def get_python_data(self, name, version=-1):
        datastore = self.datastore(name)
        cursor = datastore.find()
        data = (d.get('data') for d in cursor)
        return list(data)

    def get_object_as_python(self, meta, version=-1):
        if meta.kind == Metadata.SKLEARN_JOBLIB:
            return meta.gridfile
        if meta.kind == Metadata.PANDAS_HDF:
            return meta.gridfile
        if meta.kind == Metadata.PANDAS_DFROWS:
            return list(getattr(self.mongodb, meta.collection).find())
        if meta.kind == Metadata.PYTHON_DATA:
            col = getattr(self.mongodb, meta.collection)
            return [d.get('data') for d in col.find(dict(_id=meta.objid))]
        raise TypeError('cannot return kind %s as a python object' % meta.kind)

    def list(self, pattern=None, regexp=None, raw=False):
        """
        list all files in store

        specify pattern as a unix pattern (e.g. 'models/*', 
        or specify regexp)

        :param pattern: the unix file pattern or None for all
        :param regexp: the regexp. takes precedence over pattern
        :param raw: if True return the meta data objects
        """
        if raw:
            meta = list(Metadata.objects())
            if regexp:
                files = [f for f in meta if re.match(regexp, meta.name)]
            elif pattern:
                files = [f for f in meta if fnmatch(meta.name, pattern)]
        else:
            files = [d.name for d in Metadata.objects()]
            if regexp:
                files = [f for f in files if re.match(regexp, f)]
            elif pattern:
                files = [f for f in files if fnmatch(f, pattern)]
            files = [f.replace('.omm', '') for f in files]
        return files

    def _package_model(self, model, filename):
        """
        dump model using joblib and package all joblib files into zip 
        """
        import joblib
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
        import joblib
        lpath = tempfile.mkdtemp()
        fname = os.path.basename(packagefname).replace('.omm', '')
        mklfname = os.path.join(lpath, fname)
        with ZipFile(packagefname) as zipf:
            zipf.extractall(lpath)
        model = joblib.load(mklfname)
        rmtree(lpath)
        return model

    def _package_dataframe2hdf(self, df, filename, key=None):
        """
        package a dataframe as a hdf file
        """
        lpath = tempfile.mkdtemp()
        fname = os.path.basename(filename)
        hdffname = os.path.join(self.tmppath, fname + '.hdf')
        key = key or fname
        df.to_hdf(hdffname, key)
        return hdffname

    def _extract_dataframe_hdf(self, filename, version=-1):
        """
        extract a dataframe stored as hdf
        """
        import pandas as pd
        hdffname = os.path.join(self.tmppath, filename)
        dirname = os.path.dirname(hdffname)
        try:
            os.makedirs(dirname)
        except OSError:
            # OSError is raised if path exists already
            pass
        outf = self.fs.get_version(filename, version=version)
        with open(hdffname, 'w') as hdff:
            hdff.write(outf.read())
        hdf = pd.HDFStore(hdffname)
        key = hdf.keys()[0]
        df = hdf[key]
        hdf.close()
        return df
