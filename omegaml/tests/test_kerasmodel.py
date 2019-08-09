from unittest import TestCase

import numpy as np

from omegaml import Omega
from omegaml.backends.keras import KerasBackend


class KerasBackendTests(TestCase):
    def setUp(self):
        self.om = Omega()
        self.om.models.register_backend(KerasBackend.KIND, KerasBackend)

    def _build_model(self, fit=False):
        # build a dummy model for testing. does not need to make sense
        import keras
        from keras.models import Sequential
        from keras.layers import Dense, Dropout
        from keras.optimizers import SGD

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
        model.add(Dense(10, activation='softmax'))
        sgd = SGD(lr=0.01, decay=1e-6, momentum=0.9, nesterov=True)
        model.compile(loss='categorical_crossentropy',
                      optimizer=sgd,
                      metrics=['accuracy'])

        if fit:
            model.fit(x_train, y_train,
                      epochs=1,
                      batch_size=128)
        return model

    def test_load_save(self):
        om = self.om
        model = self._build_model(fit=True)
        om.models.put(model, 'keras-model')
        model_ = om.models.get('keras-model')
        x_test = np.random.random((100, 20))
        self.assertTrue(np.all(np.equal(model_.get_weights()[0], (model.get_weights()[0]))))

    def test_fit(self):
        import keras
        om = self.om
        model = self._build_model(fit=False)
        om.models.put(model, 'keras-model')
        x_test = np.random.random((100, 20))
        y_test = keras.utils.to_categorical(np.random.randint(10, size=(100, 1)), num_classes=10)
        result = om.runtime.model('keras-model').fit(x_test, y_test).get()
        self.assertTrue(result.startswith('<Metadata:'))
        result = om.runtime.model('keras-model').predict(x_test).get()
        self.assertEqual(result.shape, (100, 10))

    def test_predict(self):
        om = self.om
        model = self._build_model(fit=True)
        om.models.put(model, 'keras-model')
        x_test = np.random.random((100, 20))
        result = om.runtime.model('keras-model').predict(x_test).get()
        self.assertEqual(result.shape, (100, 10))






