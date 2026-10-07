from packaging.version import Version

try:
    import tensorflow as tf
except ModuleNotFoundError:
    pass
else:
    from packaging.version import Version

    if Version(tf.__version__) < Version('2.16'):
        from .tfkeras import TensorflowKerasBackend as TensorflowKerasBackend
        from .tfkerassavedmodel import TensorflowKerasSavedModelBackend as TensorflowKerasSavedModelBackend
        from .tfsavedmodel import ServingInput as ServingInput
        from .tfsavedmodel import TensorflowSavedModelBackend as TensorflowSavedModelBackend
        from .tfsavedmodel import TensorflowSavedModelPredictor as TensorflowSavedModelPredictor

        # compatibility with previous tensorflow versions
        FN_MAP = {}
        if tf.__version__.startswith('1.'):
            FN_MAP['pandas_input_fn'] = tf.estimator.inputs.pandas_input_fn
            FN_MAP['numpy_input_fn'] = tf.estimator.inputs.numpy_input_fn
            FN_MAP['convert_to_tensor'] = tf.compat.v1.convert_to_tensor
        elif tf.__version__.startswith('2.'):
            FN_MAP['pandas_input_fn'] = tf.compat.v1.estimator.inputs.pandas_input_fn
            FN_MAP['numpy_input_fn'] = tf.compat.v1.estimator.inputs.numpy_input_fn
            FN_MAP['convert_to_tensor'] = tf.convert_to_tensor

        def _tffn(name):
            return FN_MAP[name]
