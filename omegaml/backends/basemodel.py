

class BaseModelBackend(object):

    """
    OmegaML BaseModelBackend to be subclassed by other arbitrary backends

    This provides the abstract interface for any model backend to be implemented
    """
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

    def put_model(self, obj, name, attributes=None, **kwargs):
        """
        store a model

        :param obj: the model object to be stored
        :param name: the name of the object
        :param attributes: attributes for meta data
        """
        raise NotImplementedError

    def get_model(self, name, version=-1, **kwargs):
        """
        retrieve a model

        :param name: the name of the object
        :param version: the version of the object (not supported)
        """
        raise NotImplementedError

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
            self, modelname, Xname, Yname, rName=True, pure_python=True,
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
