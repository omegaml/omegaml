

class BaseBackend(object):

    """
    OmegaML BaseBackend to be subclassed by other arbitrary backends

    This provides the abstract interface for any backend to be implemented
    """

    def put_model(self, obj, name, attributes=None):
        """
        store a model

        :param obj: the model object to be stored
        :param name: the name of the object
        :param attributes: attributes for meta data
        """
        raise NotImplementedError

    def get_model(self, name, version=-1):
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
