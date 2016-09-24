

from base import BaseBackend
from mongoengine.fields import GridFSProxy
from uuid import uuid4


class SparkBackend(BaseBackend):
    """
    Spark Backend
    """
    def __init__(self, store):
        self.store = store

    def put_model(self, obj, name, attributes=None, **kwargs):
        """
        create a meta data object that is later used to submit spark jobs.
        """
        from ..documents import Metadata
        params = kwargs.get('params')
        if isinstance(obj, str):
            uri = "spark://mllib/" + str(obj)
            attributes = dict(params=params) if params else {}
            return self.store._make_metadata(
                name=name,
                prefix=self.store.prefix,
                bucket=self.store.bucket,
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
                fileid = self.store.fs.put(
                    fzip, filename=self.store._get_obj_store_key(
                        filename, 'omm'))
                gridfile = GridFSProxy(
                    grid_id=fileid,
                    db_alias='omega',
                    collection_name=self.store.bucket)
            return self.store._make_metadata(
                name=name,
                prefix=self.store.prefix,
                bucket=self.store.bucket,
                kind=Metadata.SPARK_MLLIB,
                attributes=attrs,
                gridfile=gridfile,
                uri=uri).save()

    def get_model(self, name, version=-1):
        """ return a class """
        from ..util import load_class
        meta = self.store.metadata(name, version=-1)
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
        meta = self.store.metadata(modelname)
        params = meta.attributes.get('params')
        # method train requires a DataFrame with a Vector
        # http://stackoverflow.com/a/36143084/1350619
        import omegaml as om
        dataX = om.datasets.get(Xname)
        model = self.get_model(modelname)
        sc = SparkContext.getOrCreate()
        sqlContext = SQLContext(sc)
        spark_df = sqlContext.createDataFrame(dataX)

        if Yname:
            from ..util import get_labeledpoints
            rdd = get_labeledpoints(Xname, Yname)
        else:
            rdd = spark_df.map(lambda data: Vectors.dense(
                [float(x) for x in data]))

        if params:
            try:
                result = model.train(rdd, **params)
            except Exception, e:
                from warnings import warn
                warn("Please make sure necessary parameters are provided!")
                warn("Consult http://spark.apache.org/docs/latest/api/python/pyspark.mllib.html for more information on parameters!")
                raise e
        else:
            ##
            # TBD: per model fit/train method selection
            ##
            if 'KMeans' in meta.uri:
                # using 3 clusters
                # https://git.io/v6mxX
                result = model.train(rdd, 3)
            elif 'LogisticRegressionWithLBFGS' in meta.uri:
                from omegaml.util import get_labeled_points_from_rdd
                labeled_point = get_labeled_points_from_rdd(rdd)
                result = model.train(labeled_point)
        sc.stop()
        self.put_model(result, modelname)
        return result

    def predict(
            self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        from pyspark import SparkContext, SQLContext
        import omegaml as om
        data = om.datasets.get(Xname)
        model = self.get_model(modelname)
        sc = SparkContext.getOrCreate()
        sqlContext = SQLContext(sc)
        spark_df = sqlContext.createDataFrame(data)
        result = model.predict(spark_df.rdd.map(list))
        temp_name = rName if rName else '%s_%s' % (Xname, uuid4().hex)
        meta = om.datasets.put(
            result.map(lambda x: (x, )).toDF().toPandas(), temp_name)
        sc.stop()
        result = om.datasets.get(temp_name)
        if rName:
            result = meta
        return result
