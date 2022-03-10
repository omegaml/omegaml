import unittest

import pandas as pd

from omegaml import Omega
from omegaml.backends.experiment import ExperimentBackend
from omegaml.tests.util import OmegaTestMixin
from omegaml.util import module_available


@unittest.skipUnless(module_available("tensorflow"), "tensorflow is not installed")
class TFCallbackTrackingTestCases(OmegaTestMixin, unittest.TestCase):
    """
    notes on framework versions v.v. tracing

    tensorflow
    1.15.3  - does not report metric on epoch, while later versions do
              (=> reports only 9 instead of 10 metrics per run)
            - reports metric='accuracy' as 'acc'
    """

    def setUp(self):
        self.om = om = Omega()
        self.clean()
        om.models.register_backend(ExperimentBackend.KIND, ExperimentBackend)

    def test_tensorflow_callback(self):
        om = self.om
        # fit locally
        with om.runtime.experiment('myexp') as exp:
            model, X, Y = self._create_model(exp.tensorflow_callback())
        self.assertIsInstance(exp.data(), pd.DataFrame)
        self.assertGreaterEqual(len(exp.data(key='loss')), 9)
        self.assertGreaterEqual(len(exp.data(key=['acc', 'accuracy'])), 9)
        model_ = exp.restore_artifact('model')
        self.assertIsInstance(model, type(model_))
        # fit via runtime
        om.models.put(model, 'mymodel')
        with om.runtime.experiment('myexp2') as exp:
            om.runtime.model('mymodel').fit(X, Y, epochs=1,
                                            batch_size=128).get()
        self.assertIsNotNone(exp.data())
        self.assertGreaterEqual(len(exp.data(key=['acc', 'accuracy'])), 9)

    def _create_model(self, tracking_cb):
        import numpy as np
        import tensorflow as tf
        from tensorflow import keras
        from tensorflow.keras.optimizers import SGD
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import Dense

        x_train = np.random.random((1000, 20))
        y_train = keras.utils.to_categorical(np.random.randint(10, size=(1000, 1)), num_classes=10)

        model = Sequential()
        # FIXME tv versions 2.2 through 2.6 worked with x_train.shape, 1.15.3 and since 2.7 dont
        if tf.version.VERSION == '1.15.3':
            # rationale: https://stackoverflow.com/a/43233458/890242
            x_shape = x_train.shape[1:]
        else:
            x_shape = x_train.shape
        x_shape = x_train.shape[1:]
        model.add(Dense(10, activation='softmax', input_shape=x_shape))
        sgd = SGD(lr=0.01, decay=1e-6, momentum=0.9, nesterov=True)
        model.compile(loss='categorical_crossentropy',
                      optimizer=sgd,
                      metrics=['accuracy'])
        model.fit(x_train, y_train,
                  epochs=1,
                  batch_size=128, callbacks=[tracking_cb])
        return model, x_train, y_train


if __name__ == '__main__':
    unittest.main()
