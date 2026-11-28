Working MLFlow models
=====================

.. _mlflow: https://mlflow.org/

.. contents::

omega-ml provides a single, unified API and leverages the `mlflow`_ model format
to form a cloud-agnostic runtime platform for both model building and serving.

Using mlflow saved models
-------------------------

In mlflow, models are saved using a model-specific API:

.. code:: python

    from sklearn.linear_model import LinearRegression

    model = LinearRegression()
    model_path = './models'
    mlflow.sklearn.save_model(model, model_path)

Given such a mlflow saved model, we can store the model in omega-ml and get
it back as follows:

.. code:: python

    In [1]: # use the same model_path as in mlflow's save_model
            om.models.put(model_path, 'mymodel')
            # get back the model
            mymodel = om.models.get('mymodel')
            type(mymodel)
    Out[2]:
            mlflow.pyfunc.PyFuncModel


Using a MLModel file
--------------------

When saving a model, mlflow creates a file called :code:`MLModel`. omega-ml can
also store this file directly:

.. code:: python

    In [1]: # use the same model_path as in mlflow's save_model
            om.models.put('mlflow:///path/to/MLModel', 'mymodel')
            # get back the model
            mymodel = om.models.get('mymodel')
            type(mymodel)
    Out[2]:
            mlflow.pyfunc.PyFuncModel


Using a mlflow Model or PythonModel
-----------------------------------

omega-ml can also be used inside mlflow projects to store a model directly,
without saving the model to a file first. This is useful if you like to use
a mlflow model flavor that omega-ml does not support natively.

.. code:: python

    # inside a mlflow project script
    model = LinearRegression()
    meta = om.models.put(model, 'mymodel', kind='mlflow.model')


Serving mlflow model runs
-------------------------

If you use the tracking features of mlflow, omegaml can directly serve
models from mlflow. This is useful if you use mlflow locally or in
development, and use omega-ml for easy model deployment to production, or
if you need to use a model flavor that omega-ml does not support natively.

.. code:: python

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


Model frameworks supported via mlflow
-------------------------------------

.. _mlflow_flavors: https://github.com/mlflow/mlflow/blob/master/docs/source/models.rst

The following mlflow model flavors can be stored in omega-ml. A full list of
model flavors supported by mlflow can be found at `mlflow_flavors`_

* Python
* Keras
* MLeap
* PyTorch
* Scikit-learn
* Spark MLLib
* Tensorflow
* XGBoost
* LightGBM
* FastAI
* SpaCy
* Statsmodels


Disclaimer and License
----------------------

.. _mlflow_license: https://github.com/mlflow/mlflow/blob/master/LICENSE.txt

mlflow is not part of, distributed by or along of omega-the. The above
describes API-binding interfaces to mlflow, but does not itself constitute
a derivative work of mlflow as per the `mlflow_license`_.
