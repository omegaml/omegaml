import six

from omegaml.backends.basemodel import BaseModelBackend
from omegaml.util import ensure_python_array


class KerasBackend(BaseModelBackend):
    KIND = 'keras.h5'

    @classmethod
    def supports(self, obj, name, **kwargs):
        from keras import Sequential, Model
        return isinstance(obj, (Sequential, Model))

    def _package_model(self, model, key, tmpfn):
        # https://www.tensorflow.org/api_docs/python/tf/keras/models/save_model
        # defaults to h5 since TF 2.x. We keep with h5 for simplicity for now
        import tensorflow as tf
        kwargs = dict(save_format='h5') if tf.__version__.startswith('2') else {}
        model.save(tmpfn, **kwargs)
        return tmpfn

    def _extract_model(self, infile, key, tmpfn):
        # override to implement model loading
        from keras.engine.saving import load_model
        with open(tmpfn, 'wb') as pkgf:
            pkgf.write(infile.read())
        return load_model(tmpfn)

    def fit(self, modelname, Xname, Yname=None, validation_data=None,
            pure_python=True, **kwargs):
        """
        Fit a model

        Args:
            modelname: the name of the model
            Xname: the name of the X dataset
            Yname: the name of the Y dataset
            pure_python: deprecated
            kwargs: any additional kwargs are passed on to model.fit()

        Returns:
            the meta data object of the model
        """
        meta = self.model_store.metadata(modelname)
        model = self.get_model(modelname)
        X = self.data_store.get(Xname)
        Y = self.data_store.get(Yname) if Yname else None
        keras_kwargs = dict(kwargs)
        if validation_data:
            valX, valY = validation_data
            if isinstance(X, six.string_types):
                valX = self.data_store.get(valX)
            if isinstance(Y, six.string_types):
                valY = self.data_store.get(valY)
            keras_kwargs['validation_data'] = (valX, valY)
        history = model.fit(X, Y, **keras_kwargs)
        meta = self.model_store.put(model, modelname, attributes={
            'history': serializable_history(history)
        })
        return meta

    def predict(self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        model = self.get_model(modelname)
        X = self.data_store.get(Xname)
        result = model.predict(X)
        if rName:
            meta = self.data_store.put(result, rName)
            result = meta
        return result

    def score(
          self, modelname, Xname, Yname=None, rName=True, pure_python=True,
          **kwargs):
        model = self.get_model(modelname)
        X = self.data_store.get(Xname)
        Y = self.data_store.get(Yname)
        result = model.evaluate(X, Y)
        if rName:
            meta = self.data_store.put(result, rName)
            result = meta
        return result


def serializable_history(history):
    # ensure history object is JSON/BSON serializable by converting to default
    return {k: ensure_python_array(v, float)
            for k, v in six.iteritems(history.history)}
