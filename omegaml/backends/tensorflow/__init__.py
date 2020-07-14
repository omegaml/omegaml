import tensorflow as tf

from .tfestimatormodel import TFEstimatorModelBackend, TFEstimatorModel
from .tfkeras import TensorflowKerasBackend
from .tfkerassavedmodel import TensorflowKerasSavedModelBackend
from .tfsavedmodel import TensorflowSavedModelPredictor, TensorflowSavedModelBackend, ServingInput

# compatibility with previous tensorflow versions
FN_MAP = {}
if tf.__version__.startswith('1.'):
    FN_MAP['pandas_input_fn'] = getattr(tf.estimator.inputs, 'pandas_input_fn')
    FN_MAP['numpy_input_fn'] = getattr(tf.estimator.inputs, 'numpy_input_fn')
    FN_MAP['convert_to_tensor']  = getattr(tf.compat.v1, 'convert_to_tensor')
elif tf.__version__.startswith('2.'):
    FN_MAP['pandas_input_fn'] = getattr(tf.compat.v1.estimator.inputs, 'pandas_input_fn')
    FN_MAP['numpy_input_fn'] = getattr(tf.compat.v1.estimator.inputs, 'numpy_input_fn')
    FN_MAP['convert_to_tensor'] = getattr(tf, 'convert_to_tensor')


def _tffn(name):
    return FN_MAP[name]
