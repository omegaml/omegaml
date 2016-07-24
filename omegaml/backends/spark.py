

import os
import glob
import tempfile
from base import BaseBackend
from zipfile import ZipFile, ZIP_DEFLATED
from mongoengine.fields import GridFSProxy
from shutil import rmtree
from uuid import uuid4


class SparkBackend(BaseBackend):
    """
    Spark Backend
    """
    def __init__(self, store):
        self.store = store

    def _package_model(self, model, filename):
        """
        dump model using mllib save method and package all files into zip
        """
        from pyspark import SparkContext
        try:
            sc.stop()
        except:
            pass
        sc = SparkContext()
        lpath = tempfile.mkdtemp()
        fname = os.path.basename(filename)
        mklfname = os.path.join(lpath, fname)
        zipfname = os.path.join(self.store.tmppath, fname)
        model.save(sc, mklfname)
        with ZipFile(zipfname, 'w', compression=ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(lpath):
                for name in files:
                    path = os.path.normpath(os.path.join(root, name))
                    if os.path.isfile(path):
                        zipf.write(path, os.path.join(
                            root.split('/')[-1], name))
        # rmtree(lpath)
        sc.stop()
        return zipfname

    def _extract_model(self, name, packagefname):
        """
        load model using joblib from a zip file created with _package_model
        """
        from pyspark import SparkContext
        from ..util import load_class
        try:
            sc.stop()
        except:
            pass
        sc = SparkContext()
        lpath = tempfile.mkdtemp()
        fname = os.path.basename(packagefname)
        mklfname = os.path.join(lpath, fname)
        with ZipFile(packagefname) as zipf:
            zipf.extractall(mklfname)
        meta = self.store.metadata(name, version=-1)
        spark_cls = meta.uri.split('/')[-1]
        model = load_class(spark_cls).load(sc, mklfname)
        # model = model.load(sc, mklfname)
        sc.stop()
        rmtree(lpath)
        return model

    def put_model(self, obj, name, attributes=None):
        """
        create a meta data object that is later used to submit spark jobs.
        """
        from ..documents import Metadata
        if isinstance(obj, str):
            uri = "spark://mllib/" + str(obj)
            return self.store._make_metadata(
                name=name,
                prefix=self.store.prefix,
                bucket=self.store.bucket,
                uri=uri,
                gridfile=None,
                kind=Metadata.SPARK_MLLIB).save()
        else:
            zipfname = self._package_model(obj, name)
            with open(zipfname) as fzip:
                fileid = self.store.fs.put(
                    fzip, filename=self.store._get_obj_store_key(name, 'omm'))
                gridfile = GridFSProxy(grid_id=fileid,
                                       db_alias='omega',
                                       collection_name=self.store.bucket)
                uri = "spark://mllib/" + obj.__module__ + '.' + obj.__class__.__name__
            return self.store._make_metadata(
                name=name,
                prefix=self.store.prefix,
                bucket=self.store.bucket,
                kind=Metadata.SPARK_MLLIB,
                uri=uri,
                gridfile=gridfile).save()

    def get_model(self, name, version=-1):
        """ return a class """
        from ..util import load_class
        meta = self.store.metadata(name, version=-1)
        if meta.gridfile.grid_id is not None:
            filename = self.store._get_obj_store_key(name, '.omm')
            packagefname = os.path.join(self.store.tmppath, name)
            dirname = os.path.dirname(packagefname)
            try:
                os.makedirs(dirname)
            except OSError:
                # OSError is raised if path exists already
                pass
            outf = self.store.fs.get_version(filename, version=version)
            with open(packagefname, 'w') as zipf:
                zipf.write(outf.read())
            model = self._extract_model(name, packagefname)
            return model
        else:
            spark_cls = meta.uri.split('/')[-1]
            return load_class(spark_cls)

    def fit(self, modelname, Xname, Yname=None, pure_python=True, **kwargs):
        from pyspark import SparkContext, SQLContext
        from pyspark.mllib.linalg import Vectors
        # method train requires a DataFrame with a Vector
        # http://stackoverflow.com/a/36143084/1350619
        import omegaml as om
        try:
            sc.stop()
        except:
            pass
        dataX = om.datasets.get(Xname)
        model = self.get_model(modelname)
        sc = SparkContext()
        sqlContext = SQLContext(sc)
        spark_df = sqlContext.createDataFrame(dataX)
        rdd = spark_df.map(lambda data: Vectors.dense(
            [float(x) for x in data]))
        # using 2 clusters
        # https://git.io/v6mxX
        result = model.train(rdd, 3)
        sc.stop()
        self.put_model(result, modelname)
        return result

    def predict(
            self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        from pyspark import SparkContext, SQLContext
        import omegaml as om
        try:
            sc.stop()
        except:
            pass
        data = om.datasets.get(Xname)
        model = self.get_model(modelname)
        sc = SparkContext()
        sqlContext = SQLContext(sc)
        spark_df = sqlContext.createDataFrame(data)
        result = model.predict(spark_df.rdd.map(list))
        temp_name = '%s_%s' % (Xname, uuid4().hex)
        meta = om.datasets.put(
            result.map(lambda x: (x, )).toDF().toPandas(), temp_name)
        sc.stop()
        return meta
