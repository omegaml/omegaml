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
        return model_store.prefix == 'models/' and kind == 'python.model'
