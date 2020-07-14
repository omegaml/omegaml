from inspect import isfunction
from unittest import TestCase, skip

from omegaml import Omega
from omegaml.backends.tensorflow import _tffn
from omegaml.backends.tensorflow.tfestimatormodel import TFEstimatorModelBackend, TFEstimatorModel
from omegaml.backends.virtualobj import virtualobj
from omegaml.tests.util import OmegaTestMixin, tf_perhaps_eager_execution


def make_data():
    # read data from csv
    import numpy as np
    import pandas as pd
    columns = ['f1', 'f2', 'f3', 'f4', 'f5']
    train_data = pd.DataFrame(np.random.random_sample((20, 5)),
                              columns=columns).astype(int)
    test_data = pd.DataFrame(np.random.random_sample((20, 5)),
                             columns=columns).astype(int)
    # separate train data
    train_x = train_data[columns[:-1]]
    train_y = train_data.loc[:, columns[-1]]

    # separate test data
    test_x = test_data[columns[:-1]]
    test_y = test_data.loc[:, columns[-1]]
    return train_x, train_y, test_x, test_y


def make_estimator_fn():
    # this is to ensure we get a serializable function
    def make_estimator(model_dir=None):
        import tensorflow as tf
        feature_columns = [tf.feature_column.numeric_column(key=key)
                           for key in ['f1', 'f2', 'f3', 'f4']]
        classifier = tf.estimator.LinearClassifier(feature_columns=feature_columns,
                                                   n_classes=3, model_dir=model_dir)
        return classifier

    return make_estimator


def make_input_fn():
    # create classifier and save untrained
    # we need to use a custom input_fn as the default won't be able to figure
    # out column names from numpy inputs
    def input_fn(mode, X, Y=None, batch_size=1):
        import tensorflow as tf
        X = {
            'f{}'.format(i + 1): X[:, i] for i in range(X.shape[1])
        }
        return _tffn('numpy_input_fn')(x=X, y=Y, num_epochs=1, shuffle=False)

    return input_fn


class TFEstimatorModelBackendTests(OmegaTestMixin, TestCase):
    def setUp(self):
        self.om = Omega()
        self.om.models.register_backend(TFEstimatorModelBackend.KIND, TFEstimatorModelBackend)
        self.clean()
        tf_perhaps_eager_execution()

    def test_fit_predict(self):
        import tensorflow as tf
        om = self.om
        # create classifier
        estmdl = TFEstimatorModel(estimator_fn=make_estimator_fn())
        train_x, train_y, test_x, test_y = make_data()
        classifier = estmdl.fit(train_x, train_y)
        self.assertIsInstance(classifier, tf.estimator.LinearClassifier)
        # score
        score = estmdl.score(test_x, test_y)
        self.assertIsInstance(score, dict)
        self.assertIn('accuracy', score)
        self.assertIn('loss', score)
        # predict
        predict = [v for v in estmdl.predict(test_x)]
        self.assertIsInstance(predict, list)
        self.assertIn('logits', predict[0])
        self.assertIn('probabilities', predict[0])
        self.assertIn('classes', predict[0])

    def test_fit_predict_from_numpy(self):
        import tensorflow as tf
        om = self.om
        # note we use a custom input_fn
        estmdl = TFEstimatorModel(estimator_fn=make_estimator_fn(), input_fn=make_input_fn())
        train_x, train_y, test_x, test_y = make_data()
        # create a feature dict from a numpy array
        train_x = train_x.values  # numpy
        train_y = train_y.values
        test_x = test_x.values
        classifier = estmdl.fit(train_x, train_y)
        self.assertIsInstance(classifier, tf.estimator.LinearClassifier)
        # score
        score = estmdl.score(test_x, test_y)
        self.assertIsInstance(score, dict)
        self.assertIn('accuracy', score)
        self.assertIn('loss', score)
        # predict
        predict = [v for v in estmdl.predict(test_x)]
        self.assertIsInstance(predict, list)
        self.assertIn('logits', predict[0])
        self.assertIn('probabilities', predict[0])
        self.assertIn('classes', predict[0])

    def test_save_load_unfitted(self):
        om = self.om
        # create classifier and save
        estmdl = TFEstimatorModel(estimator_fn=make_estimator_fn())
        meta = om.models.put(estmdl, 'estimator-model')
        # restore and use
        estmdl_r = om.models.get('estimator-model')
        self.assertIsInstance(estmdl_r, estmdl.__class__)
        train_x, train_y, test_x, test_y = make_data()
        estmdl_r.fit(train_x, train_y)
        predict = [v for v in estmdl.predict(test_x)]
        self.assertIsInstance(predict, list)
        self.assertIn('logits', predict[0])
        self.assertIn('probabilities', predict[0])
        self.assertIn('classes', predict[0])

    def test_save_load_estimator_model(self):
        import tensorflow as tf
        om = self.om
        # create classifier and save
        estmdl = TFEstimatorModel(estimator_fn=make_estimator_fn())
        meta = om.models.put(estmdl, 'estimator-model')
        # restore and use
        estmdl_r = om.models.get('estimator-model')
        # check we have a restored instance
        self.assertIsNot(estmdl_r, estmdl)
        self.assertNotEqual(estmdl.estimator.model_dir, estmdl_r.estimator.model_dir)
        self.assertIsInstance(estmdl_r, estmdl.__class__)
        self.assertIsNot(estmdl_r.estimator_fn, make_estimator_fn())
        self.assertTrue(isfunction(estmdl.estimator_fn))
        self.assertIsInstance(estmdl_r.estimator_fn(), tf.estimator.Estimator)

    def test_save_load_fitted(self):
        import numpy as np
        om = self.om
        # create classifier and save
        estmdl = TFEstimatorModel(estimator_fn=make_estimator_fn())
        train_x, train_y, test_x, test_y = make_data()
        estmdl.fit(train_x, train_y)
        predict = [v for v in estmdl.predict(test_x)]
        meta = om.models.put(estmdl, 'estimator-model')
        # restore and use
        estmdl_r = om.models.get('estimator-model')
        self.assertIsInstance(estmdl_r, estmdl.__class__)
        predict_r = [v for v in estmdl_r.predict(test_x)]
        self.assertIsInstance(predict_r, list)
        # make sure the model was actually reloaded from a new model_dir
        self.assertNotEqual(estmdl.estimator.model_dir, estmdl_r.estimator.model_dir)
        self.assertTrue(np.allclose(predict_r[0]['logits'], predict[0]['logits']))
        self.assertTrue(np.allclose(predict_r[0]['probabilities'], predict[0]['probabilities']))

    def test_save_load_fitted_estimator(self):
        import numpy as np
        om = self.om
        # create classifier and save
        estmdl = TFEstimatorModel(estimator_fn=make_estimator_fn())
        train_x, train_y, test_x, test_y = make_data()
        estmdl.fit(train_x, train_y)
        predict = [v for v in estmdl.predict(test_x)]
        meta = om.models.put(TFEstimatorModel(estimator_fn=make_estimator_fn(),
                                              model=estmdl.estimator), 'estimator-model')
        # restore and use
        estmdl_r = om.models.get('estimator-model')
        self.assertIsInstance(estmdl_r, estmdl.__class__)
        predict_r = [v for v in estmdl_r.predict(test_x)]
        self.assertIsInstance(predict_r, list)
        # make sure the model was actually reloaded from a new model_dir
        self.assertNotEqual(estmdl.estimator.model_dir, estmdl_r.estimator.model_dir)
        self.assertTrue(np.allclose(predict_r[0]['logits'], predict[0]['logits']))
        self.assertTrue(np.allclose(predict_r[0]['probabilities'], predict[0]['probabilities']))

    def test_save_load_fitted_inerror(self):
        import numpy as np
        om = self.om
        # create classifier and save untrained
        estmdl = TFEstimatorModel(estimator_fn=make_estimator_fn())
        om.models.put(estmdl, 'estimator-model')
        # create dataasets
        train_x, train_y, test_x, test_y = make_data()
        estmdl.fit(train_x, train_y)
        predict = [v for v in estmdl.predict(test_x)]
        # this effectively resets the model to untrained state
        # i.e. it can be reinstantiated but will not be trained
        estmdl._estimator = None
        meta = om.models.put(estmdl, 'estimator-model')
        # restore and use
        estmdl_r = om.models.get('estimator-model')
        self.assertIsInstance(estmdl_r, estmdl.__class__)
        predict_r = [v for v in estmdl_r.predict(test_x)]
        self.assertIsInstance(predict_r, list)
        # make sure the model was actually reloaded from a new model_dir
        self.assertNotEqual(estmdl.estimator.model_dir, estmdl_r.estimator.model_dir)
        # since we get back an unfitted model, predictions should be way off
        self.assertFalse(np.allclose(predict_r[0]['logits'], predict[0]['logits']))
        self.assertFalse(np.allclose(predict_r[0]['probabilities'], predict[0]['probabilities']))

    def test_runtime_fit(self):
        import pandas as pd
        om = self.om
        # create classifier and save untrained, note we use the default input_fn
        # provided by TFEstimatorModel as it deals easily with DataFrames
        estmdl = TFEstimatorModel(estimator_fn=make_estimator_fn())
        train_x, train_y, test_x, test_y = make_data()
        om.datasets.put(train_x, 'train_x', append=False)
        om.datasets.put(train_y, 'train_y', append=False)
        om.models.put(estmdl, 'estimator-model')
        meta = om.runtime.model('estimator-model').fit('train_x', 'train_y').get()
        self.assertTrue(meta.startswith('<Metadata:'))
        # predict using fitted model in runtime
        om.datasets.put(test_x, 'test_x', append=False)
        om.datasets.put(test_y, 'test_y', append=False)
        result = om.runtime.model('estimator-model').predict('test_x').get()
        self.assertIsInstance(result, pd.DataFrame)

    def test_runtime_predict_from_numpy(self):
        import pandas as pd
        om = self.om
        estmdl = TFEstimatorModel(estimator_fn=make_estimator_fn(), input_fn=make_input_fn())
        train_x, train_y, test_x, test_y = make_data()
        train_x = train_x.values  # numpy
        train_y = train_y.values
        test_x = test_x.values
        om.datasets.put(train_x, 'train_x')
        om.datasets.put(train_y, 'train_y')
        om.datasets.put(test_x, 'test_x')
        om.models.put(estmdl, 'estimator-model')
        meta = om.runtime.model('estimator-model').fit('train_x', 'train_y').get()
        self.assertTrue(meta.startswith('<Metadata:'))
        # predict using fitted model in runtime
        om.datasets.put(test_x, 'test_x', append=False)
        om.datasets.put(test_y, 'test_y', append=False)
        result = om.runtime.model('estimator-model').predict('test_x').get()
        self.assertIsInstance(result, pd.DataFrame)

    @skip("not supported yet as we don't have a good way to store feature dicts")
    def test_runtime_predict_from_numpy_default_inputfn(self):
        import pandas as pd
        om = self.om
        estmdl = TFEstimatorModel(estimator_fn=make_estimator_fn())
        train_x, train_y, test_x, test_y = make_data()

        def as_features(x, names=None):
            # convert dataframe to feature vectors suitable for numpy_inputfn
            cols = range(x.shape[1])
            x = x.values
            features = {
                'col'.format(i + 1): x[:, i] for i, col in zip(cols, names)
            }
            return features

        train_x = as_features(train_x, train_x.columns)
        train_y = train_y.values
        test_x = as_features(test_x, test_x.columns)
        om.datasets.put(train_x, 'train_x', append=False)
        om.datasets.put(train_y, 'train_y', append=False)
        om.datasets.put(test_x, 'test_x', append=False)
        om.models.put(estmdl, 'estimator-model')
        meta = om.runtime.model('estimator-model').fit('train_x', 'train_y').get()
        self.assertTrue(meta.startswith('<Metadata:'))
        # predict using fitted model in runtime
        om.datasets.put(test_x, 'test_x', append=False)
        om.datasets.put(test_y, 'test_y', append=False)
        result = om.runtime.model('estimator-model').predict('test_x').get()
        self.assertIsInstance(result, pd.DataFrame)

    def test_runtime_score(self):
        import pandas as pd
        om = self.om
        # create classifier and save untrained
        estmdl = TFEstimatorModel(estimator_fn=make_estimator_fn())
        train_x, train_y, test_x, test_y = make_data()
        om.datasets.put(train_x, 'train_x', append=False)
        om.datasets.put(train_y, 'train_y', append=False)
        om.models.put(estmdl, 'estimator-model')
        meta = om.runtime.model('estimator-model').fit('train_x', 'train_y').get()
        self.assertTrue(meta.startswith('<Metadata:'))
        # predict using fitted model in runtime
        om.datasets.put(test_x, 'test_x', append=False)
        om.datasets.put(test_y, 'test_y', append=False)
        result = om.runtime.model('estimator-model').score('test_x', 'test_y').get()
        self.assertIsInstance(result, pd.Series)
        self.assertAlmostEqual(result['accuracy'], 1.0)

    def test_predict_from_objecthandler(self):
        import tensorflow as tf
        om = self.om

        @virtualobj
        def train_xy_fn(Xname=None, Yname=None, **kwargs):
            import tensorflow as tf
            import omegaml as om
            X = om.datasets.get(Xname)
            Y = om.datasets.get(Yname)
            dataset = _tffn('pandas_input_fn')(X, Y, shuffle=True)
            return dataset

        @virtualobj
        def test_x_fn(Xname=None, **kwargs):
            import tensorflow as tf
            import omegaml as om
            X = om.datasets.get(Xname)
            dataset = _tffn('pandas_input_fn')(X, shuffle=False)
            return dataset

        # create classifier
        estmdl = TFEstimatorModel(estimator_fn=make_estimator_fn())
        train_x, train_y, test_x, test_y = make_data()
        # store actual data
        om.datasets.put(train_x, 'train_x')
        om.datasets.put(train_y, 'train_y')
        om.datasets.put(test_x, 'test_x')
        # make these virtual objects to return (the input fn that returns a) tf.data.Dataset
        om.datasets.put(train_xy_fn, 'train_data')
        om.datasets.put(test_x_fn, 'test_dataset')
        # use these datasets as an input fn
        # -- why can't we pass the Dataset directly? All objects must be executed on the same
        #    graph wich is only created by estimator.fit() before calling the input_fn.
        dataset = om.datasets.get('train_data', Xname='train_x', Yname='train_y')
        classifier = estmdl.fit(input_fn=dataset)
        self.assertIsInstance(classifier, tf.estimator.LinearClassifier)
        # predict directly
        dataset = om.datasets.get('test_dataset', Xname='test_x')
        predict = [v for v in estmdl.predict(input_fn=dataset)]
        self.assertIsInstance(predict, list)
        self.assertIn('logits', predict[0])
        self.assertIn('probabilities', predict[0])
        self.assertIn('classes', predict[0])
        # do the same thing on the runtime
        om.models.put(estmdl, 'estimator-model')
        meta = om.runtime.model('estimator-model').fit('train_data{Xname=train_x,Yname=train_y}').get()
        self.assertTrue(meta.startswith('<Metadata:'))
