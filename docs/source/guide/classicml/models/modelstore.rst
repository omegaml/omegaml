Introduction to models
======================

omega-ml deploys any Python machine learning model that is either serializable or pip-packagable.
The following frameworks are known to work out of the box. Additional frameworks can be easily
added by writing a plugin.

**Classic ML**

* scikit-learn
* XGBoost
* Keras
* Tensorflow
* PyTorch
* any MLFlow model (classic ML)

**Generative AI**

* OpenAI-compatible model servers like LocalAI, vLLM
* Spacy
* Gensim
* Huggingface

Storing models
--------------

Storing models and pipelines is as straight forward as storing Pandas DataFrames and Series.
Simply create the model, then use :code:`om.models.put()` to store:

.. code::

    from sklearn.linear_model import LinearRegression

    # train a linear regression model
    df = pd.DataFrame(dict(x=range(10), y=range(20,30)))
    clf = LinearRegression()
    clf.fit(df[['x']], df[['y']])
    # store the trained model
    om.models.put(clf, 'lrmodel')

Models can also be stored untrained:

.. code::

    df = pd.DataFrame(dict(x=range(10), y=range(20,30)))
    clf = LinearRegression()
    # store the trained model
    om.models.put(clf, 'lrmodel')

Using models to predict
-----------------------

Retrieving a model is equally straight forward:

.. code::

    clf = om.models.get('lrmodel')
    clf
    =>
    LinearRegression(copy_X=True, fit_intercept=True, n_jobs=1, normalize=False)

Once retrieved the model can be accessed as any model kept in memory, e.g.
to predict using new data:

.. code::

    clf = om.models.get('lrmodel')
    df = pd.DataFrame(dict(x=range(70,80)))
    clf.predict(df[['x']])
    =>
    array([[ 90.],
       [ 91.],
       [ 92.],
       [ 93.],
       [ 94.],
       [ 95.],
       [ 96.],
       [ 97.],
       [ 98.],
       [ 99.]])


Model versioning
----------------

By default all models are versioned automatically. A model is a saved instance of the model
that is connected to the same name. The following example will store two model versions, the first is not
trained and thus cannot be used for prediction, the second is fitted and thus can be used for prediction:

.. code:: python

    reg = LinearRegression()
    om.models.put(reg, 'mymodel')

    reg.fit(X, Y)
    om.models.put(reg, 'mymodel')


Model versions can be accessed by specifying the version as part of the name:

.. code:: python

    # get the latest model, note @latest is implied if not specified
    om.models.get('mymodel')
    om.models.get('mymodel@latest`)

Previous versions can be referenced by specifying :code:`^` for each previous version, or by
specifying a tag on storage:

.. code:: python

    # retrieve one version before latest
    om.models.get('mymodel^`)
    # retrieve two versions before latest
    om.models.get('mymodel^^`)

    # store a new version, give it a name
    om.models.put('mymodel', tag='experiment')
    # retrieve the @experiment model
    om.models.get('mymodel@experiment')

To see all revisions of a model use :code:`om.models.revisions('mymodel')`

.. code:: python

    om.models.revisions('mymodel')
    =>
    [('e05bd064dbc9258df929d4099a02ad5452d73389', ''),
    ('aef452194c1671e5b8a496bfbbba75d83bb51b91', ''),
    ('3ca9aef680612bbfa0d2ac67a1b2bdbd73b976f0', ['latest', 'experiment'])]

Note version naming works across all parts of omega-ml, e.g.

.. code:: python

    # use the runtime to work with a particular model version
    om.runtime.model('mymodel@experiment').fit(...)

    # works by the cli, too
    $ om runtime model 'mymodel@experiment' fit ...

    # works on the API, too
    $ curl http://hostname/api/v1/model/mymodel@experiment/fit?datax=...&datay...


Using the compute cluster
-------------------------

Prediction
++++++++++

omega-ml provides a state-of-the art compute cluster, called the *runtime*. Using
the runtime you can delegate model tasks to the cluster:

.. code::

    model = om.runtime.model('lrmodel')
    result = model.predict(df[['x']])
    result.get()
    =>
    array([[ 20.],
       [ 21.],
       [ 22.],
       [ 23.],
       [ 24.],
       [ 25.],
       [ 26.],
       [ 27.],
       [ 28.],
       [ 29.]])

Note that the :code:`result` is a deferred object that we resolve using
:code:`get`.

Instead of passing data, you may also pass the name of a DataFrame stored
in omegaml:

.. code::

    # create a dataframe and store it
    df = pd.DataFrame(dict(x=range(70,80)))
    om.datasets.put(df, 'testlrmodel')
    # use it to predict
    result = om.runtime.model('lrmodel').predict('testlrmodel')
    result.get()

Model Fitting
+++++++++++++

To train a model using the runtime, use the :code:`fit` method on the runtime's model, as you would
on a local model:

.. code::

   # create a dataframe and store it
   df = pd.DataFrame(dict(x=range(10), y=range(20,30)))
   om.datasets.put(df, 'testlrmodel')
   # use it to fit the model
   result = om.runtime.model('lrmodel').fit('testlrmodel[x]', 'testlrmodel[y]')
   result.get()


GridSearch
++++++++++

**currently supported for sckit-learn**

To use cross validated grid search on a model, use the :code:`gridsearch` method on the runtime's model. This
creates, fits and stores a :code:`GridSearchCV` instance and automatically links it to the model. Use the
GridSearchCV model to evaluate the performance of multiple parameter settings.

.. note::

    Instead of using this default implementation of :code:`GridSearchCV` you may create your
    own :code:`GridSearchCV` instance locally and then fit it using the runtime. In this case
    be sure to link the model used for grid searching and the original model by changing the
    attributes on the model's metadata.

.. code::

        X, y = make_classification()
        logreg = LogisticRegression()
        om.models.put(logreg, 'logreg')
        params = {
            'C': [0.1, 0.5, 1.0]
        }
        # gridsearch on runtime
        om.runtime.model('logreg').gridsearch(X, y, parameters=params)
        meta = om.models.metadata('logreg')
        # check gridsearch was saved
        self.assertIn('gridsearch', meta.attributes)
        self.assertEqual(len(meta.attributes['gridsearch']), 1)
        self.assertIn('gsModel', meta.attributes['gridsearch'][0])
        # check we can get back the gridsearch model
        gs_model = om.models.get(meta.attributes['gridsearch'][0]['gsModel'])
        self.assertIsInstance(gs_model, GridSearchCV)


Model Metadata
++++++++++++++

Whenever you fit a model using the runtime, it's `Metadata.attributes` will
automatically record the parameters used for fitting.

.. code:: Python

    result = om.runtime.model('mymodel').fit('sample[x]', 'sample[y]').get()
    meta = om.models('mymodel')
    meta.attributes['dataset']
    =>
    {
        'Xname': 'sample[x]',  # the X dataset
        'Yname': 'sample[y]',  # the Y dataset
        'metaX': { ... }, # Metadata for this model (at time of fit)
        'metaY': { ... }, # Metadata for this model (at time of fit)
        ...
    }

This information is also used in prediction when no dataset is provided as
input.

.. code:: Python

    om.runtime.model('mymodel').predict('*')
    # is equivalent to using meta.attributes['dataset']['Xname']
    om.runtime.model('mymodel').predict('sample[x]')

If you want a different dataset for prediction than the one you used for
training, you may change it at any time:

.. code:: Python

    # set the name of the dataset to a different name
    om.models.link_dataset('mymodel', Xname='live[x]')

    # live[x] will now be used as the default dataset for prediction
    om.runtime.model('mymodel').predict('*')
    # is equivalent to
    om.runtime.model('mymodel').predict('live[x]')


Other Model tasks
+++++++++++++++++

The runtime provides more than just model training and prediction. The runtime implements
a common API to all supported backends that follows the scikit-learn estimator model. That is the
runtime supports the following methods on a model:

* :code:`fit`
* :code:`partial_fit`
* :code:`transform`
* :code:`score`
* :code:`gridsearch`

For details refer to the API reference.

