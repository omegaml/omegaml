import os

from mongoengine import GridFSProxy


class BaseModelBackend(object):
    """
    OmegaML BaseModelBackend to be subclassed by other arbitrary backends

    This provides the abstract interface for any model backend to be implemented
    """
    _backend_version_tag = '_om_backend_version'
    _backend_version = '1'

    def __init__(self, model_store=None, data_store=None, **kwargs):
        assert model_store, "Need a model store"
        assert data_store, "Need a data store"
        self.model_store = model_store
        self.data_store = data_store

    @classmethod
    def supports(self, obj, name, **kwargs):
        """
        test if this backend supports this obj
        """
        return False

    def get(self, name, **kwargs):
        """
        retrieve a model

        :param name: the name of the object
        :param version: the version of the object (not supported)
        """
        # support new backend architecture while keeping back compatibility
        return self.get_model(name, **kwargs)

    def put(self, obj, name, **kwargs):
        """
        store a model

        :param obj: the model object to be stored
        :param name: the name of the object
        :param attributes: attributes for meta data
        """
        # support new backend architecture while keeping back compatibility
        return self.put_model(obj, name, **kwargs)

    def _tmp_packagefn(self, name):
        filename = os.path.join(self.model_store.tmppath, name)
        dirname = os.path.dirname(filename)
        os.makedirs(dirname, exist_ok=True)
        return filename

    def _store_file(self, infile, filename):
        gridfile = GridFSProxy(db_alias='omega',
                               collection_name=self.model_store._fs_collection)
        with open(infile, 'rb') as pkgf:
            gridfile.put(pkgf, filename=filename)
        return gridfile

    def _package_model(self, model, key, tmpfn, **kwargs):
        """
        implement this method to serialize a model to the given tmpfn

        Args:
            model:
            key:
            tmpfn:
            **kwargs:

        Returns:
            tmpfn or absolute path of serialized file
        """
        raise NotImplementedError

    def _extract_model(self, infile, key, tmpfn, **kwargs):
        """
        implement this method to deserialize a model from the given infile

        Args:
            infile: this is a file-like object supporting read() and seek(). if
                deserializing from this does not work directly, use tmpfn
            key:
            tmpfn:
            **kwargs:

        Returns:
            model instance
        """
        raise NotImplementedError

    def get_model(self, name, version=-1, **kwargs):
        """
        Retrieves a pre-stored model
        """
        meta = self.model_store.metadata(name)
        storekey = self.model_store.object_store_key(name, 'omm', hashed=True)
        model = self._extract_model(meta.gridfile, storekey, self._tmp_packagefn(storekey), **kwargs)
        return model

    def put_model(self, obj, name, attributes=None, _kind_version=None, **kwargs):
        """
        Packages a model using joblib and stores in GridFS
        """
        storekey = self.model_store.object_store_key(name, 'omm', hashed=True)
        tmpfn = self._tmp_packagefn(storekey)
        packagefname = self._package_model(obj, storekey, tmpfn, **kwargs) or tmpfn
        gridfile = self._store_file(packagefname, storekey)
        kind_meta = {
            self._backend_version_tag: self._backend_version,
        }
        return self.model_store._make_metadata(
            name=name,
            prefix=self.model_store.prefix,
            bucket=self.model_store.bucket,
            kind=self.KIND,
            kind_meta=kind_meta,
            attributes=attributes,
            gridfile=gridfile).save()

    def predict(
          self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        """
        predict using data stored in Xname

        :param modelname: the name of the model object
        :param Xname: the name of the X data set
        :param rName: the name of the result data object or None
        :param pure_python: if True return a python object. If False return
            a dataframe. Defaults to True to support any client.
        :param kwargs: kwargs passed to the model's predict method
        :return: return the predicted outcome
        """
        raise NotImplementedError

    def predict_proba(
          self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        """
        predict the probability using data stored in Xname

        :param modelname: the name of the model object
        :param Xname: the name of the X data set
        :param rName: the name of the result data object or None
        :param pure_python: if True return a python object. If False return
            a dataframe. Defaults to True to support any client.
        :param kwargs: kwargs passed to the model's predict method
        :return: return the predicted outcome
        """
        raise NotImplementedError

    def fit(self, modelname, Xname, Yname=None, pure_python=True, **kwargs):
        """
        fit the model with data

        :param modelname: the name of the model object
        :param Xname: the name of the X data set
        :param Yname: the name of the Y data set
        :param pure_python: if True return a python object. If False return
           a dataframe. Defaults to True to support any client.
        :param kwargs: kwargs passed to the model's predict method
        :return: return the meta data object of the model
        """
        raise NotImplementedError

    def partial_fit(
          self, modelname, Xname, Yname=None, pure_python=True, **kwargs):
        """
        partially fit the model with data (online)

        :param modelname: the name of the model object
        :param Xname: the name of the X data set
        :param Yname: the name of the Y data set
        :param pure_python: if True return a python object. If False return
           a dataframe. Defaults to True to support any client.
        :param kwargs: kwargs passed to the model's predict method
        :return: return the meta data object of the model
        """

        raise NotImplementedError

    def fit_transform(
          self, modelname, Xname, Yname=None, rName=None, pure_python=True,
          **kwargs):
        """
        fit and transform using data

        :param modelname: the name of the model object
        :param Xname: the name of the X data set
        :param Yname: the name of the Y data set
        :param rName: the name of the transforms's result data object or None
        :param pure_python: if True return a python object. If False return
           a dataframe. Defaults to True to support any client.
        :param kwargs: kwargs passed to the model's transform method
        :return: return the meta data object of the model
        """
        raise NotImplementedError

    def transform(self, modelname, Xname, rName=None, **kwargs):
        """
        transform using data

        :param modelname: the name of the model object
        :param Xname: the name of the X data set
        :param rName: the name of the transforms's result data object or None
        :param kwargs: kwargs passed to the model's transform method
        :return: return the transform data of the model
        """
        raise NotImplementedError

    def score(
          self, modelname, Xname, Yname=None, rName=True, pure_python=True,
          **kwargs):
        """
        score using data

        :param modelname: the name of the model object
        :param Xname: the name of the X data set
        :param Yname: the name of the Y data set
        :param rName: the name of the transforms's result data object or None
        :param pure_python: if True return a python object. If False return
           a dataframe. Defaults to True to support any client.
        :param kwargs: kwargs passed to the model's predict method
        :return: return the score result
        """
        raise NotImplementedError
