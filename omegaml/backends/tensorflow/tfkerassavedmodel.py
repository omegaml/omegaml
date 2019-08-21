import tempfile

from omegaml.backends.tensorflow import TensorflowSavedModelBackend


class TensorflowKerasSavedModelBackend(TensorflowSavedModelBackend):
    KIND = 'tfkeras.savedmodel'

    @classmethod
    def supports(self, obj, name, **kwargs):
        import tensorflow as tf
        tfSequential = tf.keras.models.Sequential
        tfModel = tf.keras.models.Model
        return isinstance(obj, (tfSequential, tfModel)) and kwargs.get('as_savedmodel')

    def _make_savedmodel(self, obj, serving_input_receiver_fn=None, strip_default_attrs=None):
        # https://www.tensorflow.org/api_docs/python/tf/keras/experimental/export_saved_model
        import tensorflow as tf
        export_dir = tempfile.mkdtemp()
        tf.contrib.saved_model.save_keras_model(obj, export_dir,
                                                input_signature=[tf.TensorSpec(shape=obj.input.shape,
                                                                               dtype=obj.input.dtype,
                                                                               name='input')])
        return export_dir

    def fit(self, modelname, Xname, Yname=None, pure_python=True, tpu_specs=None, **kwargs):
        raise ValueError('cannot fit a saved model')
