# import glob
import glob
import logging
import os
import tempfile
from copy import copy
from inspect import isfunction
from zipfile import ZipFile, ZIP_DEFLATED

import dill
from mongoengine import GridFSProxy

from omegaml.backends import BaseModelBackend

ok = lambda v, vtype: isinstance(v, vtype)

logger = logging.getLogger(__name__)



class TFEstimatorModel(object):
    """
    A serializable/deserizable wrapper for a TF Estimator

    Usage:
        estimator = TFEstimatorModel(estimator_fn)
        estimator.fit(input_fn=input_fn)
        estimator.predict(input_fn=input_fn)

        The estimator_fn returns a tf.estimator.Estimator or subclass.
    """

    def __init__(self, estimator_fn, model=None, input_fn=None, model_dir=None):
        """

        Args:
            estimator_fn (func): the function to return a valid tf.estimator.Estimator instance. Called as
                                 fn(model_dir=)
            model (tf.Estimator): an existing e.g. pre-fitted Estimator instance, optional. If not specified,
                                  the model will be recreated by calling estimator_fn. If specified, the
                                  model's weights and parameters will be saved and reloaded so that a fitted
                                  model can be used without further training.
            input_fn (func|dict): the function to create the input_fn as fn(mode, X, Y, batch_size=n), where mode
                                  is either 'fit', 'evaluate', or 'predict'. If not provide defaults to an input_fn
                                  that tries to infer the correct input_fn from the method and input arguments. If
                                  provided as a dict, must contain the 'fit', 'evaluate' and 'predict' keys where
                                  each value is a valid input_fn as fn(X, Y, batch_size=n).
            model_dir (str): the model directory to use. Defaults to whatever estimator_fn/Estimator instance sets
        """
        self.estimator_fn = estimator_fn
        self._model_dir = model_dir
        self._estimator = model
        self._input_fn = input_fn

    @property
    def model_dir(self):
        return self.estimator.model_dir

    @property
    def estimator(self):
        if self._estimator is None:
            self._estimator = self.estimator_fn(model_dir=self._model_dir)
        return self._estimator

    def restore(self, model_dir):
        self._estimator = None
        self._model_dir = model_dir
        return self

    def make_input_fn(self, mode, X, Y=None, batch_size=1):
        """
        Return a tf.data.Dataset from the input provided

        Args:
            mode (str): calling mode, either 'fit', 'predict' or 'evaluate'
            X (NDArray|Tensor|Dataset): features, or Dataset of (features, labels)
            Y (NDArray|Tensor|Dataset): labels, optional

        Notes:
            X can be a Dataset of (features, labels), or just features. If X is
            just features, also provide a Dataset of just labels.

            If X, Y are NDArrays or Tensors, Dataset.from_tensor_slices((dict(X), Y))
            is used to create the Dataset. If only X is provided as a NDArray or Tensor,
            only X is used to create the Dataset.

            If none of these options work, create your own input_fn and pass it
            to the .fit/.predict methods using the input_fn= kwarg
        """
        import tensorflow as tf
        import pandas as pd
        import numpy as np

        if self._input_fn is not None:
            if isinstance(self._input_fn, dict):
                return self._input_fn[mode](X, Y=Y, batch_size=batch_size)
            else:
                return self._input_fn(mode, X, Y=Y, batch_size=batch_size)

        def input_fn():
            # if we have a dataset, use that
            if isinstance(X, tf.data.Dataset):
                if Y is None:
                    return X
                elif isinstance(Y, tf.data.Dataset):
                    return X.zip(Y)
                else:
                    return X, Y
            # if we have a dataframe, create a dataset from it
            if ok(X, pd.DataFrame) and ok(Y, pd.Series):
                dataset = tf.data.Dataset.from_tensor_slices((dict(X), Y))
                result = dataset.batch(batch_size)
            elif ok(X, pd.DataFrame):
                dataset = tf.data.Dataset.from_tensor_slices(dict(X))
                result = dataset.batch(batch_size)
            else:
                result = X, Y
            return result

        if isinstance(X, (dict, np.ndarray)):
            input_fn = tf.estimator.inputs.numpy_input_fn(x=X, y=Y, num_epochs=1, shuffle=False)
        return input_fn

    def fit(self, X=None, Y=None, input_fn=None, batch_size=100, **kwargs):
        """
        Args:
           X (Dataset|ndarray): features
           Y (Dataset|ndarray): labels, optional
        """
        assert (ok(X, object) or ok(input_fn, object)), "specify either X, Y or input_fn, not both"
        if input_fn is None:
            input_fn = self.make_input_fn('fit', X, Y, batch_size=batch_size)
        return self.estimator.train(input_fn=input_fn, **kwargs)

    def score(self, X=None, Y=None, input_fn=None, batch_size=100, **kwargs):
        """
        Args:
           X (Dataset|ndarray): features
           Y (Dataset|ndarray): labels, optional
        """
        assert (ok(X, object) or ok(input_fn, object)), "specify either X, Y or input_fn, not both"
        if input_fn is None:
            input_fn = self.make_input_fn('score', X, Y, batch_size=batch_size)
        return self.estimator.evaluate(input_fn=input_fn)

    def predict(self, X=None, Y=None, input_fn=None, batch_size=1, **kwargs):
        """
        Args:
           X (Dataset|ndarray): features
           Y (Dataset|ndarray): labels, optional
        """
        options1 = (X is None) and (input_fn is not None)
        options2 = (X is not None) and (input_fn is None)
        assert options1 or options2, "specify either X, Y or input_fn, not both"
        if input_fn is None:
            input_fn = self.make_input_fn('predict', X, Y, batch_size=batch_size)
        return self.estimator.predict(input_fn=input_fn)


class TFEstimatorModelBackend(BaseModelBackend):
    KIND = 'tfestimator.model'

    @classmethod
    def supports(self, obj, name, **kwargs):
        return isinstance(obj, TFEstimatorModel)

    def _package_model(self, obj, filename):
        model_dir = obj.model_dir
        fname = os.path.basename(filename)
        zipfname = os.path.join(self.model_store.tmppath, fname)
        # get relevant parts of model_dir
        with ZipFile(zipfname, 'w', compression=ZIP_DEFLATED) as zipf:
            zipf.writestr('modelobj.dill', dill.dumps(obj))
            for part in glob.glob(os.path.join(model_dir, '*')):
                arcname = os.path.basename(part)
                if arcname == 'modelobj.dill':
                    # ignore pre-existing model
                    continue
                zipf.write(part, arcname)
        return zipfname

    def _extract_model(self, packagefname):
        lpath = tempfile.mkdtemp()
        fname = os.path.basename(packagefname)
        mklfname = os.path.join(lpath, fname)
        with ZipFile(packagefname) as zipf:
            zipf.extractall(lpath)
        with open(os.path.join(lpath, 'modelobj.dill'), 'rb') as fin:
            model = dill.load(fin)
        model.restore(lpath)
        return model

    def put_model(self, obj, name, attributes=None):
        # create a copy so we can reset the model dir
        # this is required so the model path does not get restored on get
        obj = copy(obj)
        obj._model_dir = None
        zipfname = self._package_model(obj, name)
        with open(zipfname, 'rb') as fzip:
            fileid = self.model_store.fs.put(
                fzip, filename=self.model_store._get_obj_store_key(name, '.tfm'))
            gridfile = GridFSProxy(grid_id=fileid,
                                   db_alias='omega',
                                   collection_name=self.model_store.bucket)
        return self.model_store._make_metadata(
            name=name,
            prefix=self.model_store.prefix,
            bucket=self.model_store.bucket,
            kind=self.KIND,
            attributes=attributes,
            gridfile=gridfile).save()

    def get_model(self, name, version=-1):
        filename = self.model_store._get_obj_store_key(name, '.tfm')
        packagefname = os.path.join(self.model_store.tmppath, name)
        dirname = os.path.dirname(packagefname)
        try:
            os.makedirs(dirname)
        except OSError:
            # OSError is raised if path exists already
            pass
        outf = self.model_store.fs.get_version(filename, version=version)
        with open(packagefname, 'wb') as zipf:
            zipf.write(outf.read())
        # restore the model, this will also set the model_dir
        model = self._extract_model(packagefname)
        return model

    def fit(self, modelname, Xname, Yname=None, pure_python=True, **kwargs):
        model = self.model_store.get(modelname)
        X = self.data_store.get(Xname)
        Y = self.data_store.get(Yname) if Yname else None
        if isfunction(X) and Y is None:
            # support f
            model.fit(input_fn=X)
        else:
            model.fit(X, Y)
        meta = self.model_store.put(model, modelname)
        return meta

    def predict(
            self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        import pandas as pd
        model = self.model_store.get(modelname)
        X = self.data_store.get(Xname)
        if isfunction(X):
            result = pd.DataFrame(v for v in model.predict(input_fn=X))
        else:
            result = pd.DataFrame(v for v in model.predict(X))
        if rName is not None:
            result = self.data_store.put(result, rName)
        return result

    def score(
            self, modelname, Xname, Yname, rName=True, pure_python=True,
            **kwargs):
        import pandas as pd
        model = self.model_store.get(modelname)
        X = self.data_store.get(Xname)
        Y = self.data_store.get(Yname)
        if isfunction(X) and Y is None:
            # support f
            result = model.fit(input_fn=X)
        else:
            result = model.score(X, Y)
        if not pure_python:
            result = pd.Series(result)
        if rName is not None:
            result = self.data_store.put(result, rName)
        return result
