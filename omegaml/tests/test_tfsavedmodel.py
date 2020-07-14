from unittest import TestCase, skipIf

from omegaml import Omega
from omegaml.backends.tensorflow.tfsavedmodel import TensorflowSavedModelBackend, TensorflowSavedModelPredictor
from omegaml.tests.util import OmegaTestMixin, tf_in_eager_execution


class TensorflowSavedModelBackendTests(OmegaTestMixin, TestCase):
    def setUp(self):
        self.om = Omega()
        self.om.models.register_backend(TensorflowSavedModelBackend.KIND, TensorflowSavedModelBackend)
        self.clean()

    def _build_model(self):
        # build a dummy model for testing. does not need to make sense
        import tensorflow as tf
        from omegaml.backends.tensorflow import _tffn

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
        model.add(Dense(64, activation='relu', input_dim=20, name='X'))
        model.add(Dropout(0.5))
        model.add(Dense(64, activation='relu'))
        model.add(Dropout(0.5))
        model.add(Dense(10, activation='softmax'))
        sgd = SGD(lr=0.01, decay=1e-6, momentum=0.9, nesterov=True)
        model.compile(loss='categorical_crossentropy',
                      optimizer=sgd,
                      metrics=['accuracy'])

        # https://www.tensorflow.org/guide/estimators
        est_model = tf.keras.estimator.model_to_estimator(keras_model=model)
        train_input_fn = _tffn('numpy_input_fn')(
            x={"X_input": x_train},
            y=y_train,
            num_epochs=1,
            shuffle=False)

        est_model.train(train_input_fn)
        return est_model

    @skipIf(tf_in_eager_execution(), "cannot run in eager mode")
    def test_save_load_tf_example(self):
        import tensorflow as tf
        import numpy as np

        om = self.om
        model = self._build_model()

        # https://www.tensorflow.org/guide/saved_model#prepare_serving_inputs
        default_batch_size = 1
        feature_spec = {'X_input': tf.FixedLenFeature(dtype=np.float32, shape=(20,))}

        def serving_input_receiver_fn():
            """An input receiver that expects a serialized tf.Example."""
            serialized_tf_example = tf.placeholder(dtype=tf.string,
                                                   shape=[default_batch_size],
                                                   name='X_input')
            receiver_tensors = {'X_input': serialized_tf_example}
            features = tf.parse_example(serialized_tf_example, feature_spec)
            return tf.estimator.export.ServingInputReceiver(features, receiver_tensors)

        x_test = np.random.random((100, 20))
        def input_fn():
            X = tf.data.Dataset.from_tensor_slices(x_test)
            return X.batch(1)
        yhat = [v for v in model.predict(input_fn=input_fn)]
        om.models.put(model, 'estimator-savedmodel',
                      serving_input_fn=serving_input_receiver_fn)
        self.assertIn('estimator-savedmodel', om.models.list())
        model_ = om.models.get('estimator-savedmodel')
        self.assertIsInstance(model_, TensorflowSavedModelPredictor)
        for i in range(x_test.shape[0]):
            example = tf.train.Example(features=tf.train.Features(feature={
                'X_input': tf.train.Feature(float_list=tf.train.FloatList(value=x_test[i, :]))
            }))
            yhat_ = model_.predict([example.SerializeToString()])
            self.assertTrue(np.allclose(yhat_, yhat[i][model_.output_names[0]]))

    @skipIf(tf_in_eager_execution(), "cannot run in eager mode")
    def test_save_load_native(self):
        import tensorflow as tf
        import numpy as np

        om = self.om
        model = self._build_model()

        # https://www.tensorflow.org/guide/saved_model#prepare_serving_inputs
        default_batch_size = 1

        def serving_input_receiver_fn():
            placeholder = tf.placeholder(dtype=np.float32,
                                         shape=(default_batch_size, 20),
                                         name='X_input')
            receiver_tensors = {'X_input': placeholder}
            features = {'X_input': placeholder}
            return tf.estimator.export.ServingInputReceiver(features, receiver_tensors)

        x_test = np.random.random((100, 20))
        def input_fn():
            X = tf.data.Dataset.from_tensor_slices(x_test)
            return X.batch(1)
        yhat = [v for v in model.predict(input_fn=input_fn)]
        om.models.put(model, 'estimator-savedmodel',
                      serving_input_fn=serving_input_receiver_fn)
        self.assertIn('estimator-savedmodel', om.models.list())
        model_ = om.models.get('estimator-savedmodel')
        self.assertIsInstance(model_, TensorflowSavedModelPredictor)
        for i in range(x_test.shape[0]):
            yhat_ = model_.predict([x_test[i]])
            self.assertTrue(np.allclose(yhat_, yhat[i][model_.output_names[0]]))

    def test_prediction_restapi(self):
        import tensorflow as tf
        import numpy as np

        om = self.om
        model = self._build_model()

        default_batch_size = 1
        def serving_input_receiver_fn():
            placeholder = tf.placeholder(dtype=np.float32,
                                         shape=(default_batch_size, 20),
                                         name='X_input')
            receiver_tensors = {'X_input': placeholder}
            features = {'X_input': placeholder}
            return tf.estimator.export.ServingInputReceiver(features, receiver_tensors)



