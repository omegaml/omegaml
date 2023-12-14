import warnings
from itertools import product


class TensorflowCallbackBase:
    """ A callback for Tensorflow Keras models

    Implements the callback protocol according to Tensorflow Keras
    semantics and linking to a :class:`omegaml.backends.tracking.TrackingProvider`

    See Also:

        * https://www.tensorflow.org/guide/keras/custom_callback
    """

    #
    def __new__(cls, *args, **kwargs):
        # generate methods as per specs
        for action, phase in product(['train', 'test', 'predict'], ['begin', 'end']):
            cls.wrap(f'on_{action}_{phase}', 'on_global')
            cls.wrap(f'on_{action}_batch_{phase}', 'on_batch')
        for phase in ['begin', 'end']:
            cls.wrap(f'on_epoch_{phase}', 'on_epoch')
        return super().__new__(cls)

    def __init__(self, tracker):
        self.tracker = tracker
        self.model = None

    def set_model(self, model):
        self.tracker.log_artifact(model, 'model')

    def set_params(self, params):
        for k, v in params.items():
            self.tracker.log_param(k, v)

    def on_global(self, action, logs=None):
        for k, v in (logs or {}).items():
            self.tracker.log_metric(k, v, step=0)

    def on_batch(self, action, batch, logs=None):
        for k, v in (logs or {}).items():
            self.tracker.log_metric(k, v, step=batch)

    def on_epoch(self, action, epoch, logs=None):
        for k, v in (logs or {}).items():
            self.tracker.log_metric(k, v, step=epoch)

    @classmethod
    def wrap(cls, method, fn):
        fn = getattr(cls, fn)

        def inner(self, *args, **kwargs):
            return fn(self, method, *args, **kwargs)

        setattr(cls, method, inner)
        return inner


try:
    from tensorflow import keras
except Exception as e:
    class TensorflowCallback(TensorflowCallbackBase):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            warnings.warn(f'tensorflow could not be loaded, TensorflowCallback may not work due to {e}')
else:
    class TensorflowCallback(TensorflowCallbackBase, keras.callbacks.Callback):
        pass
