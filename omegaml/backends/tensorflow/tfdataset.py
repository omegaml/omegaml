from omegaml.backends.basedata import BaseDataBackend

class TFDatasetBackend(BaseDataBackend):
    KIND = 'tf.dataset'

    @classmethod
    def supports(self, obj, name, **kwargs):
        import tensorflow as tf
        return isinstance(obj, )

    def put(self, obj, name, attributes=None, **kwargs):
        pass
