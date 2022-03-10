import os
import unittest
import warnings
from shutil import rmtree
from unittest import TestCase

import pandas as pd
from numpy.testing import assert_array_equal
from sklearn.linear_model import LinearRegression

import omegaml.defaults
from omegaml import Omega
from omegaml.tests.util import OmegaTestMixin
from omegaml.util import reshaped, module_available

try:
    from omegaml.backends.mlflow.models import MLFlowModelBackend
    from omegaml.backends.mlflow.registrymodels import MLFlowRegistryBackend
except:
    warnings.warn("mlflow is not installed")
else:
    from mlflow.exceptions import MlflowException

    @unittest.skipUnless(module_available('mlflow'), 'mlflow not available')
    class TestMLFlowModels(OmegaTestMixin, TestCase):
        def setUp(self):
            om = self.om = Omega()
            self.clean()
            om.models.register_backend(MLFlowModelBackend.KIND, MLFlowModelBackend)
            om.models.register_backend(MLFlowRegistryBackend.KIND, MLFlowRegistryBackend)

        def test_save_mlflow_saved_model_path(self):
            """ test deploying a model saved by MLflow, from path """
            import mlflow

            model_path = os.path.join(omegaml.defaults.OMEGA_TMP, 'mymodel')
            model = LinearRegression()
            X = pd.Series(range(0, 10))
            Y = pd.Series(X) * 2 + 3
            model.fit(reshaped(X), reshaped(Y))
            rmtree(model_path, ignore_errors=True)
            mlflow.sklearn.save_model(model, model_path)

            om = self.om
            # store with just the model path, specify the kind because paths can be other files too
            meta = om.models.put(model_path, 'mymodel', kind='mlflow.model')
            self.assertEqual(meta.kind, MLFlowModelBackend.KIND)
            model_ = om.models.get('mymodel')
            self.assertIsInstance(model_, mlflow.pyfunc.PyFuncModel)
            yhat_direct = model_.predict(reshaped(X))
            yhat_rt = om.runtime.model('mymodel').predict(X).get()
            assert_array_equal(yhat_rt, yhat_direct)

        def test_save_mlflow_saved_model_file(self):
            """ test deploying model saved by MLFlow, by file """
            import mlflow

            model_path = os.path.join(omegaml.defaults.OMEGA_TMP, 'mymodel')
            model = LinearRegression()
            X = pd.Series(range(0, 10))
            Y = pd.Series(X) * 2 + 3
            model.fit(reshaped(X), reshaped(Y))
            rmtree(model_path, ignore_errors=True)
            mlflow.sklearn.save_model(model, model_path)

            om = self.om
            # test multiple ways of storing
            for fn in ('mlflow://' + os.path.join(model_path, 'MLmodel'),
                       'mlflow://' + model_path):
                # store with just the MLmodel file as a reference, no kind necessary
                om.models.drop('mymodel', force=True)
                meta = om.models.put(fn, 'mymodel')
                self.assertEqual(meta.kind, MLFlowModelBackend.KIND)
                self.assertEqual(meta.kind, MLFlowModelBackend.KIND)
                model_ = om.models.get('mymodel')
                self.assertIsInstance(model_, mlflow.pyfunc.PyFuncModel)
                yhat_direct = model_.predict(reshaped(X))
                yhat_rt = om.runtime.model('mymodel').predict(X).get()
                assert_array_equal(yhat_rt, yhat_direct)

        def test_save_mlflow_pyfunc_model(self):
            """ test deploying a custom MLFlow PythonModel"""
            import mlflow

            class MyModel(mlflow.pyfunc.PythonModel):
                def predict(self, context, data):
                    return data

            X = pd.Series(range(10))
            model = MyModel()
            om = self.om
            meta = om.models.put(model, 'mymodel')
            self.assertEqual(meta.kind, MLFlowModelBackend.KIND)
            model_ = om.models.get('mymodel')
            self.assertIsInstance(model_, mlflow.pyfunc.PyFuncModel)
            yhat_direct = model_.predict(X)
            yhat_rt = om.runtime.model('mymodel').predict(X).get()
            assert_array_equal(yhat_rt, reshaped(yhat_direct))

        def test_inferred_model_flavor(self):
            """ test deploying an arbitrary model by inferring MLFlow flavor """
            import mlflow

            om = self.om
            model = LinearRegression()
            X = pd.Series(range(0, 10))
            Y = pd.Series(X) * 2 + 3
            model.fit(reshaped(X), reshaped(Y))
            meta = om.models.put(model, 'mymodel', kind='mlflow.model')
            self.assertEqual(meta.kind, MLFlowModelBackend.KIND)
            model_ = om.models.get('mymodel')
            self.assertIsInstance(model_, mlflow.pyfunc.PyFuncModel)

        def test_save_mlflow_model_run(self):
            """ test deploying an MLModel from a tracking server URI """
            import mlflow

            mlflow.set_tracking_uri('sqlite:///mlflow.sqlite')
            with mlflow.start_run() as run:
                model = LinearRegression()
                X = pd.Series(range(0, 10))
                Y = pd.Series(X) * 2 + 3
                model.fit(reshaped(X), reshaped(Y))
                mlflow.sklearn.log_model(sk_model=model,
                                         artifact_path='sklearn-model',
                                         registered_model_name='sklearn-model')

            om = self.om
            # store with just the model path, specify the kind because paths can be other files too
            meta = om.models.put('mlflow+models://sklearn-model/1', 'sklearn-model')
            self.assertEqual(meta.kind, MLFlowRegistryBackend.KIND)
            model_ = om.models.get('sklearn-model')
            self.assertIsInstance(model_, mlflow.pyfunc.PyFuncModel)
            yhat_direct = model_.predict(reshaped(X))
            yhat_rt = om.runtime.model('sklearn-model').predict(X).get()
            assert_array_equal(yhat_rt, yhat_direct)

        def test_save_mlflow_model_run_file_tracking(self):
            """ test deploying an MLModel from a tracking URI using file path (not supported) """
            import mlflow

            om = self.om
            # note we don't set a tracking uri so mlflow uses a local file path and refused to
            # work with the file path as a model registry
            mlflow.set_tracking_uri(None)
            with self.assertRaises(MlflowException):
                meta = om.models.put('mlflow+models://sklearn-model/1', 'sklearn-model')
            self.assertNotIn('sklearn-model', om.models.list())

