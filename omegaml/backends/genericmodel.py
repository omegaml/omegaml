import joblib

from omegaml.backends.basemodel import BaseModelBackend


class GenericModelBackend(BaseModelBackend):
    """ a generic model backend enabling custom serializers

    supports arbitrary model saving and loading for use in a @virtualobj function

    Usage:
        # save any model
        om.models.put(model, 'name', kind='python.model',
                        serializer=lambda store, model, filename: ...)

        # load any model
        model = om.models.get(model, 'name',
                        loader=lambda store, filename: ...)

        # use a virtualobj to load the model with a custom loader
        @virtualobj
        def mymodel(*args, **kwargs):
            model = om.models.get(model, 'name',
                        loader=lambda store, filename: ...)

    See Also:
        - TestPytorchModels.test_pytorch_model_genericmodel

    .. versionadded:: NEXT
        backend kind='python.model' supports custom serializers
    """
    KIND = 'python.model'

    serializer = lambda store, model, filename, **kwargs: joblib.dump(model, filename)[0]
    loader = lambda store, infile, filename=None, **kwargs: joblib.load(infile)

    @classmethod
    def supports(cls, obj, name, model_store=None, kind=None, **kwargs):
        explicit = model_store.prefix == 'models/' and kind == 'python.model'
        implicit = model_store.prefix == 'models/' and isinstance(obj, tuple) and callable(obj[-1])
        implicit |= any(callable(kwargs.get(k)) for k in ('serializer', 'loader'))
        return explicit or implicit

    def put(self, obj, name, uri=None, serializer=None, loader=None, **kwargs):
        """ save any model using custom serializer and loader

        Args:
            obj (any|tuple): model instance or a tuple of (instance, helper), where
                helper is a @virtualobj callable that will be used as the helper
            name (str): name of the object
            uri (str): optional, the path to a storage location supported by smart_open,
             if not provided defaults to metadata.gridfile
            serializer (callable): a callable, serializer(store, model, filename, **kwargs),
               where store is self, model is obj, filename is the /path/to/file of the
               serialized object. serializer() must return the actual filename or None
            loader (callable): a callable, loader(store, infile, **kwargs), where
               store is self, infile is the opened file-like object to be read from.
               loader() must return the deserialized model object
            **kwargs (dict): optional, passed on to delegate .put(), the delegate being
              either the helper, super(), or another backend suitable for this model

        Returns:
            metadata (Metadata): the metadata object created from this object
        """
        if isinstance(obj, tuple) and callable(obj[-1]):
            # assume a helper has been provided, store it and pass along
            model, vobj = obj
            helper_name = f'.helpers/{name}'
            self.model_store.put(vobj, helper_name, replace=True, noversion=True)
            kwargs.update(helper=helper_name)
        else:
            # just a model, no helper
            model = obj
        if callable(serializer) or callable(loader):
            # BaseModelbackend will handle serializer and loader
            return super().put(model, name, uri=uri, serializer=serializer, loader=loader, **kwargs)
        # called explicitly, use normal backend
        return self.model_store.put(model, name, uri=uri, **kwargs)
