

from __future__ import absolute_import
from omegaml.backends.basemodel import BaseModelBackend
from mongoengine.fields import GridFSProxy
from uuid import uuid4


class SparkBackend(BaseModelBackend):
    """
    OmegaML backend to use with Spark installations
    """

    def __init__(self, model_store=None, data_store=None, **kwargs):
        self.SPARK_MLLIB_TRAINERS = {
            'pyspark.mllib.clustering.KMeans': 'train_kmeans',
            'pyspark.mllib.classification.LogisticRegressionWithLBFGS':
            'train_logisticregressionwithlbfgs',
        }
        # FIXME adapt to model_store and data_store attributes
        self.model_store = model_store
        self.data_store = data_store

    def put_model(self, obj, name, attributes=None, **kwargs):
        """
        Creates a metadata object that is later used to submit spark jobs.
        """
        from ..documents import Metadata
        params = kwargs.get('params')
        if isinstance(obj, str):
            uri = "spark://mllib/" + str(obj)
            attributes = dict(params=params) if params else {}
            return self.model_store._make_metadata(
                name=name,
                prefix=self.model_store.prefix,
                bucket=self.model_store.bucket,
                uri=uri,
                attributes=attributes,
                gridfile=None,
                kind=Metadata.SPARK_MLLIB).save()
        else:
            from pyspark import SparkContext
            filename = '%s_%s' % (name, uuid4().hex)
            sc = SparkContext.getOrCreate()
            obj.save(sc, filename)
            uri = "spark://mllib/" + obj.__module__ + '.' + obj.__class__.__name__
            sc.stop()
            attrs = {'hdfs_filename': filename}
            with open(filename, 'w+') as fzip:
                fileid = self.model_store.fs.put(
                    fzip, filename=self.model_store._get_obj_store_key(
                        filename, 'omm'))
                gridfile = GridFSProxy(
                    grid_id=fileid,
                    db_alias='omega',
                    collection_name=self.model_store.bucket)
            return self.model_store._make_metadata(
                name=name,
                prefix=self.model_store.prefix,
                bucket=self.model_store.bucket,
                kind=Metadata.SPARK_MLLIB,
                attributes=attrs,
                gridfile=gridfile,
                uri=uri).save()

    def get_model(self, name, version=-1):
        """
        Returns a pre-stored model or a spark ml library class dependent on the
        content and type of metadata stored
        """
        from ..util import load_class
        meta = self.model_store.metadata(name, version=-1)
        if meta.gridfile.grid_id is not None:
            from pyspark import SparkContext
            sc = SparkContext.getOrCreate()
            spark_cls = meta.uri.split('/')[-1]
            model = load_class(spark_cls).load(
                sc, meta.attributes.get('hdfs_filename'))
            sc.stop()
            return model
        else:
            spark_cls = meta.uri.split('/')[-1]
            return load_class(spark_cls)

    def fit(self, modelname, Xname, Yname=None, pure_python=True, **kwargs):
        from pyspark import SparkContext, SQLContext
        from pyspark.mllib.linalg import Vectors
        meta = self.model_store.metadata(modelname)
        params = meta.attributes.get('params')
        # method train requires a DataFrame with a Vector
        # http://stackoverflow.com/a/36143084/1350619
        dataX = self.data_store.get(Xname)
        model = self.get_model(modelname)
        sc = SparkContext.getOrCreate()
        sqlContext = SQLContext(sc)
        spark_df = sqlContext.createDataFrame(dataX)

        if Yname:
            from ..util import get_labeledpoints
            rdd = get_labeledpoints(Xname, Yname)
        else:
            rdd = spark_df.rdd.map(lambda data: Vectors.dense(
                [float(x) for x in data]))

        mllib = meta.uri.rsplit('spark://mllib/')[1]

        trainer_method = self.SPARK_MLLIB_TRAINERS.get(mllib)

        if trainer_method is None:
            raise NotImplementedError
        else:
            trainer = getattr(self, trainer_method)

        result = trainer(model, rdd, params)

        sc.stop()
        self.put_model(result, modelname)
        return result

    def predict(
            self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        from pyspark import SparkContext, SQLContext
        data = self.data_store.get(Xname)
        model = self.get_model(modelname)
        sc = SparkContext.getOrCreate()
        sqlContext = SQLContext(sc)
        spark_df = sqlContext.createDataFrame(data)
        result = model.predict(spark_df.rdd.map(list))
        temp_name = rName if rName else '%s_%s' % (Xname, uuid4().hex)
        meta = self.data_store.put(
            result.map(lambda x: (x, )).toDF().toPandas(), temp_name)
        sc.stop()
        result = self.data_store.get(temp_name)
        if rName:
            result = meta
        return result

    def train_kmeans(self, model, rdd, params):
        """
        Trains a model using KMeans
        """
        try:
            if params is None:
                result = model.train(rdd)
            else:
                result = model.train(rdd, **params)
        except Exception as e:
            from warnings import warn
            warn("Please make sure necessary parameters are provided!")
            warn("Consult http://spark.apache.org/docs/latest/api/python/pyspark.mllib.html for more information on parameters!")
            raise e
        return result

    def train_logisticregressionwithlbfgs(self, model, rdd, params):
        """
        Trains a model using logistic regression
        """
        from omegaml.util import get_labeled_points_from_rdd
        labeled_point = get_labeled_points_from_rdd(rdd)
        try:
            if params is None:
                result = model.train(labeled_point)
            else:
                result = model.train(labeled_point, **params)
        except Exception as e:
            from warnings import warn
            warn("Please make sure necessary parameters are provided!")
            warn("Consult http://spark.apache.org/docs/latest/api/python/pyspark.mllib.html for more information on parameters!")
            raise e
        return result
