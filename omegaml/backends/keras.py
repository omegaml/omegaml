import os

import six
from mongoengine import GridFSProxy

from omegaml.backends import BaseModelBackend
from omegaml.util import temp_filename, remove_temp_filename, ensure_python_array

import numpy as np


class KerasBackend(BaseModelBackend):
    KIND = 'keras.h5'

    @classmethod
    def supports(self, obj, name, **kwargs):
        from keras import Sequential, Model
        return isinstance(obj, (Sequential, Model))

    def _save_model(self, model, fn):
        # override to implement model saving
        model.save(fn)

    def _load_model(self, fn):
        # override to implement model loading
        from keras.engine.saving import load_model
        return load_model(fn)

    def put_model(self, obj, name, attributes=None, **kwargs):
        fn = temp_filename()
        self._save_model(obj, fn)
        with open(fn, mode='rb') as fin:
            fileid = self.model_store.fs.put(
                fin, filename=self.model_store._get_obj_store_key(name, 'h5'))
            gridfile = GridFSProxy(grid_id=fileid,
                                   db_alias='omega',
                                   collection_name=self.model_store.bucket)
        remove_temp_filename(fn)
        return self.model_store._make_metadata(
            name=name,
            prefix=self.model_store.prefix,
            bucket=self.model_store.bucket,
            kind=self.KIND,
            attributes=attributes,
            gridfile=gridfile).save()

    def get_model(self, name, version=-1):
        filename = self.model_store._get_obj_store_key(name, 'h5')
        packagefname = os.path.join(self.model_store.tmppath, name)
        dirname = os.path.dirname(packagefname)
        try:
            os.makedirs(dirname)
        except OSError:
            # OSError is raised if path exists already
            pass
        outf = self.model_store.fs.get_version(filename, version=version)
        with open(packagefname, 'wb') as fout:
            fout.write(outf.read())
        model = self._load_model(packagefname)
        return model

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
        meta = self.put_model(model, modelname, attributes={
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
            self, modelname, Xname, Yname, rName=True, pure_python=True,
            **kwargs):
        model = self.get_model(modelname)
        X = self.data_store.get(Xname)
        Y = self.data_store.get(Yname)
        score = model.evaluate(X, Y)
        return score


def serializable_history(history):
    # ensure history object is JSON/BSON serializable by converting to default
    return {k: ensure_python_array(v, float)
            for k, v in six.iteritems(history.history)}
