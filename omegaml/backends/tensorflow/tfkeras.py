import os

from omegaml.backends.keras import KerasBackend
from omegaml.util import temp_filename


class TensorflowKerasBackend(KerasBackend):
    KIND = 'tfkeras.h5'

    @classmethod
    def supports(self, obj, name, **kwargs):
        import tensorflow as tf
        tfSequential = tf.keras.models.Sequential
        tfModel = tf.keras.models.Model
        return isinstance(obj, (tfSequential, tfModel)) and not kwargs.get('as_savedmodel')

    def _save_model(self, model, fn):
        # override to implement model saving
        import tensorflow as tf
        from tensorflow import keras
        if tf.executing_eagerly():
            self._fix_model_for_saving(model)
        keras.models.save_model(model, fn)

    def _fix_model_for_saving(self, model):
        # see
        import tensorflow as tf
        from tensorflow.python.keras import backend as K
        with K.name_scope(model.optimizer.__class__.__name__):
            try:
                for i, var in enumerate(model.optimizer.weights):
                    name = 'variable{}'.format(i)
                    model.optimizer.weights[i] = tf.Variable(var, name=name)
            except NotImplementedError:
                pass

    def _extract_model(self, infile, key, tmpfn):
        # override to implement model loading
        from tensorflow import keras
        with open(tmpfn, 'wb') as pkgfn:
            pkgfn.write(infile.read())
        return keras.models.load_model(tmpfn)

    def fit(self, modelname, Xname, Yname=None, pure_python=True, tpu_specs=None, **kwargs):
        meta = self.model_store.metadata(modelname)
        tpu_specs = tpu_specs or meta.attributes.get('tpu_specs')
        if tpu_specs:
            try:
                result = self._fit_tpu(modelname, Xname, Yname, tpu_specs=tpu_specs, **kwargs)
            except:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning('Error in _fit_tpu, reverting to fit on CPU')
            else:
                return result
        result = super(TensorflowKerasBackend, self).fit(modelname, Xname, Yname=Yname, pure_python=pure_python,
                                                         **kwargs)
        return result

    def _fit_tpu(self, modelname, Xname, Yname=None, tpu_specs=None, **kwargs):
        import tensorflow as tf
        # adopted from https://www.dlology.com/blog/how-to-train-keras-model-x20-times-faster-with-tpu-for-free/
        # This address identifies the TPU we'll use when configuring TensorFlow.
        # FIXME this will fail in tf 2.0, see https://github.com/tensorflow/tensorflow/issues/24412#issuecomment-491980177
        assert tf.__version__.startswith('1.'), "TPU only supported on tf < 2.0"
        tpu_device = tpu_specs or os.environ.get('COLAB_TPU_ADDR', '')
        assert tpu_device, "there is no TPU device"
        if tpu_device.startswith('grpc://'):
            tpu_worker = tpu_device
        else:
            tpu_worker = 'grpc://' + tpu_device
        tf.logging.set_verbosity(tf.logging.INFO)
        model = self.get_model(modelname)
        tpu_model = tf.contrib.tpu.keras_to_tpu_model(
            model,
            strategy=tf.contrib.tpu.TPUDistributionStrategy(
                tf.contrib.cluster_resolver.TPUClusterResolver(tpu_worker)))
        X = self.data_store.get(Xname)
        Y = self.data_store.get(Yname)
        tpu_model.fit(X, Y)
        fn = temp_filename()
        tpu_model.save_weights(fn, overwrite=True)
        model.load_weights(fn)
        meta = self.put(model, modelname)
        return meta
