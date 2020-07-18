import glob
import os
import tempfile
from shutil import rmtree
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
import tensorflow as tf
from tensorflow.python.framework.ops import EagerTensor

from omegaml.backends.basemodel import BaseModelBackend


class TensorflowSavedModelPredictor(object):
    """
    A predictor model from a TF SavedModel
    """

    def __init__(self, model_dir):
        self.model_dir = model_dir
        if tf.__version__.startswith('1'):
            self.__init_tf_v1()
        else:
            self.__init__tf_v2()

    def __init__tf_v2(self):
        imported = tf.saved_model.load(self.model_dir)
        if callable(imported):
            self.predict_fn = imported
        else:
            self.predict_fn = imported.signatures["serving_default"]
        self.inputs = imported.signatures["serving_default"].inputs
        self.outputs = imported.signatures["serving_default"].outputs
        self._convert_to_model_input = self._convert_to_model_input_v2
        self._convert_to_model_output = self._convert_to_model_output_v2

    def __init_tf_v1(self):
        from tensorflow.contrib import predictor
        self.predict_fn = predictor.from_saved_model(self.model_dir)
        self.input_names = list(self.predict_fn.feed_tensors.keys())
        self.output_names = list(self.predict_fn.fetch_tensors.keys())
        self._convert_to_model_input = self._convert_to_model_input_v1
        self._convert_to_model_output = self._convert_to_model_output_v1

    def _convert_to_model_input_v1(self, X):
        # coerce input into expected feature mapping
        model_input = {
            self.input_names[0]: X
        }
        return model_input

    def _convert_to_model_input_v2(self, X):
        # coerce input into expected feature mapping
        from omegaml.backends.tensorflow import _tffn
        return _tffn('convert_to_tensor')(X,
                                          name=self.inputs[0].name,
                                          dtype=self.inputs[0].dtype)

    def _convert_to_model_output_v1(self, yhat):
        # coerce output into dict or array-like response
        if len(self.output_names) == 1:
            yhat = yhat[self.output_names[0]]
        return yhat

    def _convert_to_model_output_v2(self, yhat):
        # coerce output into dict or array-like response
        return yhat

    def predict(self, X):
        yhat = self.predict_fn(self._convert_to_model_input(X))
        return self._convert_to_model_output(yhat)


class TensorflowSavedModelBackend(BaseModelBackend):
    KIND = 'tf.savedmodel'
    _model_ext = 'tfsm'

    @classmethod
    def supports(self, obj, name, **kwargs):
        import tensorflow as tf
        return isinstance(obj, (tf.estimator.Estimator, tf.compat.v1.estimator.Estimator))

    def _package_model(self, model, key, tmpfn, serving_input_fn=None,
                       strip_default_attrs=None, **kwargs):
        export_dir_base = self._make_savedmodel(model, serving_input_receiver_fn=serving_input_fn,
                                                strip_default_attrs=strip_default_attrs)
        zipfname = self._package_savedmodel(export_dir_base, key)
        rmtree(export_dir_base)
        return zipfname

    def _extract_model(self, infile, key, tmpfn, **kwargs):
        with open(tmpfn, 'wb') as pkgfn:
            pkgfn.write(infile.read())
        model = self._extract_savedmodel(tmpfn)
        return model

    def _package_savedmodel(self, export_base_dir, filename):
        fname = os.path.basename(filename)
        zipfname = os.path.join(self.model_store.tmppath, fname)
        # check if we have an intermediate directory (timestamp)
        # as in export_base_dir/<timestamp>, if so, use this as the base directory
        # see https://www.tensorflow.org/guide/saved_model#perform_the_export
        # we need this check because not all SavedModel exports create a timestamp
        # directory. e.g. keras.save_keras_model() does not, while Estimator.export_saved_model does
        files = glob.glob(os.path.join(export_base_dir, '*'))
        if len(files) == 1:
            export_base_dir = files[0]
        with ZipFile(zipfname, 'w', compression=ZIP_DEFLATED) as zipf:
            for part in glob.glob(os.path.join(export_base_dir, '**'), recursive=True):
                zipf.write(part, os.path.relpath(part, export_base_dir))
        return zipfname

    def _extract_savedmodel(self, packagefname):
        lpath = tempfile.mkdtemp()
        fname = os.path.basename(packagefname)
        mklfname = os.path.join(lpath, fname)
        with ZipFile(packagefname) as zipf:
            zipf.extractall(lpath)
        model = TensorflowSavedModelPredictor(lpath)
        rmtree(lpath)
        return model

    def _make_savedmodel(self, obj, serving_input_receiver_fn=None, strip_default_attrs=None):
        # adapted from https://www.tensorflow.org/guide/saved_model#perform_the_export
        export_dir_base = tempfile.mkdtemp()
        obj.export_savedmodel(export_dir_base,
                              serving_input_receiver_fn=serving_input_receiver_fn,
                              strip_default_attrs=strip_default_attrs)
        return export_dir_base

    def predict(
          self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        """
        Predict from a SavedModel

        Args:
            modelname:
            Xname:
            rName:
            pure_python:
            kwargs:

        Returns:

        """
        model = self.get_model(modelname)
        X = self.data_store.get(Xname)
        result = model.predict(X)

        def ensure_serializable(data):
            # convert to numpy
            if isinstance(data, dict):
                for k, v in data.items():
                    data[k] = ensure_serializable(v)
            elif isinstance(data, EagerTensor):
                data = data.numpy()
                if pure_python:
                    data = data.tolist()
            return data

        result = ensure_serializable(result)

        if rName:
            result = self.data_store.put(result, rName)
        return result

    def fit(self, modelname, Xname, Yname=None, pure_python=True, tpu_specs=None, **kwargs):
        raise ValueError('cannot fit a saved model')


class ServingInput(object):
    # FIXME this is not working yet
    def __init__(self, model=None, features=None, like=None, shape=None, dtype=None,
                 batchsize=1, from_keras=False, v1_compat=False):
        """
        Helper to create serving_input_fn

        Uses tf.build_raw_serving_input_receiver_fn to build a ServingInputReceiver
        from the given inputs

        Usage:
            # use existing ndarray e.g. training or test data to specify a single input feature
            ServingInput(features=['x'], like=ndarray)

            # specify the dtype and shape explicitely
            ServingInput(features=['x'], shape=(1, 28, 28))

            # use multiple features
            ServingInput(features={'f1': tf.Feature(...))

            # for tf.keras models turned estimator, specify from_keras
            # to ensure the input features are renamed correctly.
            ServingInput(features=['x'], like=ndarray, from_keras=True)

        Args:
            model:
            features:
            like:
            shape:
            dtype:
            batchsize:
            from_keras:
        """
        self.model = model
        self.features = features or ['X']
        self.like = like
        self.shape = shape
        self.dtype = dtype
        self.batchsize = batchsize
        self.from_keras = from_keras
        self.v1_compat = v1_compat

    def build(self):
        if isinstance(self.features, dict):
            input_fn = self.from_features()
        elif isinstance(self.like, np.ndarray):
            shape = tuple((self.batchsize, *self.like.shape[1:]))  # assume (rows, *cols)
            input_fn = self.from_ndarray(shape, self.like.dtype)
        elif isinstance(self.shape, (list, tuple, np.ndarray)):
            input_fn = self.from_ndarray(self.shape, self.dtype)
        return input_fn

    def __call__(self):
        input_fn = self.build()
        return input_fn()

    @property
    def tf(self):
        if self.v1_compat:
            # https://www.tensorflow.org/guide/migrate
            import tensorflow.compat.v1 as tf
            tf.disable_v2_behavior()
        else:
            import tensorflow as tf
        return tf

    def from_features(self):
        tf = self.tf
        input_fn = tf.estimator.export.build_raw_serving_input_receiver_fn(
            self.features,
            default_batch_size=self.batchsize
        )
        return input_fn

    def from_ndarray(self, shape, dtype):
        tf = self.tf
        if self.from_keras:
            input_layer_name = '{}_input'.format(self.features[0])
        else:
            input_layer_name = self.features[0]
        if self.v1_compat:
            features = {
                input_layer_name: tf.placeholder(dtype=dtype, shape=shape, )
            }
        else:
            features = {
                input_layer_name: tf.TensorSpec(shape=shape, dtype=dtype)
            }
        input_fn = tf.estimator.export.build_raw_serving_input_receiver_fn(
            features,
            default_batch_size=None
        )
        return input_fn

    def from_dataframe(self, columns, input_layer_name='X',
                       batch_size=1, dtype=np.float32):
        def serving_input_fn():
            import tensorflow as tf
            ndim = len(columns)
            X_name = '{}_input'.format(input_layer_name)
            placeholder = tf.placeholder(dtype=np.float32,
                                         shape=(batch_size, ndim),
                                         name=X_name)
            receiver_tensors = {X_name: placeholder}
            features = {X_name: placeholder}
            return tf.estimator.export.ServingInputReceiver(features, receiver_tensors)
