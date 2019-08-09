import warnings
from unittest import TestCase

import sys

import os


class OmegaTestMixin(object):
    def clean(self):
        drop = self.om.models.drop
        [drop(m, force=True) for m in self.om.models]
        drop = self.om.datasets.drop
        [drop(m, force=True) for m in self.om.datasets]


def tf_in_eager_execution():
    # condition for unittest.skipIf decorator
    import tensorflow as tf
    return tf.executing_eagerly()

def tf_perhaps_eager_execution(*args, **kwargs):
    """
    test support to enable tf eager execution

    conditionally set eager execution if TF_EAGER env
    variable is yet to 1. else the eager state is not
    changed.
    """
    tf_eager_switch = os.environ.get('TF_EAGER', False)
    if int(tf_eager_switch):
        import tensorflow as tf
        try:
            tf.enable_eager_execution(*args, **kwargs)
            warnings.warn('TensorFlow eager execution enabled')
        except ValueError as e:
            warnings.warn(str(e))
    else:
        warnings.warn('TensorFlow eager execution not enabled TF_EAGER={tf_eager_switch}'.format(**locals()))




