from omegaml.backends.basecommon import BackendBaseCommon


class BaseDataBackend(BackendBaseCommon):

    """
    OmegaML BaseDataBackend to be subclassed by other arbitrary backends

    This provides the abstract interface for any data backend to be implemented
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

    def put(self, obj, name, attributes=None, **kwargs):
        """
        put an obj

        :param obj: the object to store (object)
        :param name: the name of the object (str)
        :param attributes: the attributes dict (dict, optional)
        :param kwargs: other kwargs to be passed to the Metadata object
        :return: the Metadata object
        """
        raise NotImplementedError

    def get(self, name, version=-1, force_python=False, lazy=False, **kwargs):
        """
        get an obj

        :param name: the name of the object (str)
        :return: the object as it was originally stored
        """
        raise NotImplementedError

    def getl(self, *args, **kwargs):
        """
        get an lazy implementation to access the obj

        A lazy implementation is a proxy to the object that can be
        evaluated using the :code:`.value` property. The proxy should
        ensure that any operations applied on the object are delayed until
        the .value property is accessed. Typically this is to ensure that
        the actual computation is executed on the cluster, not on the local
        machine.

        :param name: the name of the object (str)
        :return: the proxy to the object as it was originally stored
        """
        return self.get(*args, lazy=True, **kwargs)
