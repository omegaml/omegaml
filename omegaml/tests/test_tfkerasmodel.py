from unittest import TestCase

import numpy as np

from omegaml import Omega
from omegaml.backends.tensorflow import TensorflowSavedModelPredictor
from omegaml.backends.tensorflow.tfkeras import TensorflowKerasBackend
from omegaml.backends.tensorflow.tfkerassavedmodel import TensorflowKerasSavedModelBackend
from omegaml.tests.util import OmegaTestMixin, tf_perhaps_eager_execution


class TensorflowKerasBackendTests(OmegaTestMixin, TestCase):
    def setUp(self):
        self.om = Omega()
        self.om.models.register_backend(TensorflowKerasBackend.KIND, TensorflowKerasBackend)
        self.om.models.register_backend(TensorflowKerasSavedModelBackend.KIND, TensorflowKerasSavedModelBackend)
        self.clean()
        tf_perhaps_eager_execution()

    def _build_model(self, fit=False):
        # build a dummy model for testing. does not need to make sense
        import tensorflow as tf
        keras = tf.keras
        Sequential = keras.models.Sequential
        Dense = keras.layers.Dense
        Dropout = keras.layers.Dropout
        SGD = keras.optimizers.SGD

        # Generate dummy data
        import numpy as np
        x_train = np.random.random((1000, 20))
        y_train = keras.utils.to_categorical(np.random.randint(10, size=(1000, 1)), num_classes=10)
        x_test = np.random.random((100, 20))
        y_test = keras.utils.to_categorical(np.random.randint(10, size=(100, 1)), num_classes=10)

        model = Sequential()
        # Dense(64) is a fully-connected layer with 64 hidden units.
        # in the first layer, you must specify the expected input data shape:
        # here, 20-dimensional vectors.
        model.add(Dense(64, activation='relu', input_dim=20))
        model.add(Dropout(0.5))
        model.add(Dense(64, activation='relu'))
        model.add(Dropout(0.5))
        model.add(Dense(10, activation='softmax', name='output'))
        sgd = SGD(lr=0.01, decay=1e-6, momentum=0.9, nesterov=True)
        model.compile(loss='categorical_crossentropy',
                      optimizer=sgd,
                      metrics=['accuracy'])

        if fit:
            model.fit(x_train, y_train,
                      epochs=1,
                      batch_size=128)
        return model

    def test_save_load(self):
        om = self.om
        model = self._build_model(fit=True)
        om.models.put(model, 'keras-model')
        model_ = om.models.get('keras-model')
        self.assertTrue(np.all(np.equal(model_.get_weights()[0], (model.get_weights()[0]))))

    def test_fit(self):
        from tensorflow import keras
        om = self.om
        model = self._build_model(fit=False)
        om.models.put(model, 'keras-model')
        x_test = np.random.random((100, 20))
        y_test = keras.utils.to_categorical(np.random.randint(10, size=(100, 1)), num_classes=10)
        result = om.runtime.model('keras-model').fit(x_test, y_test).get()
        self.assertTrue(result.startswith('<Metadata:'))
        result = om.runtime.model('keras-model').predict(x_test, epochs=10).get()
        self.assertEqual(result.shape, (100, 10))

    def test_fit_tpu(self):
        from tensorflow import keras
        om = self.om
        model = self._build_model(fit=False)
        om.models.put(model, 'keras-model')
        x_test = np.random.random((100, 20))
        y_test = keras.utils.to_categorical(np.random.randint(10, size=(100, 1)), num_classes=10)
        result = om.runtime.model('keras-model').fit(x_test, y_test, tpu_specs=True).get()
        self.assertTrue(result.startswith('<Metadata:'))
        result = om.runtime.model('keras-model').predict(x_test).get()
        self.assertEqual(result.shape, (100, 10))

    def test_runtime_predict_from_trained_model(self):
        om = self.om
        model = self._build_model(fit=True)
        om.models.put(model, 'keras-model')
        x_test = np.random.random((100, 20))
        result = om.runtime.model('keras-model').predict(x_test).get()
        self.assertEqual(result.shape, (100, 10))

    def test_save_load_savedmodel(self):
        om = self.om
        model = self._build_model(fit=True)
        x_test = np.random.random((100, 20))
        yhat = model.predict(x_test)
        om.models.put(model, 'keras-savedmodel', as_savedmodel=True)
        model_ = om.models.get('keras-savedmodel')
        self.assertIsInstance(model_, TensorflowSavedModelPredictor)
        yhat_ = model_.predict(x_test)
        self.assertTrue(np.allclose(yhat_, yhat))






