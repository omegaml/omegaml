Using the runtime for MLOps
===========================

.. contents::


:code:`om.runtime` provides access to cloud resources:

Training a model
----------------

Training a model using a cloud cluster is straight forward:

.. code:: python

    # store some data and an unfitted model
    pd = pd.DataFrame({'x': range(100))
    reg = LinearRegression()
    om.models.put(reg, 'mymodel')

    # train the model using the cloud
    om.runtime.model('mymodel').fit('sample[x]', 'sample[y]')

The same also works from the command line:

.. code:: bash

    $ om datasets put sample.csv sample
    $ om models put mymodel.create_model mymodel
    $ om runtime model mymodel fit sample[x] sample[y]


Using a model for prediction
----------------------------

.. code:: python

    X = pd.Series(...)
    result = om.runtime.model('mymodel').predict(X)
    yhat = result.get()


Scoring a model
---------------

.. code:: python

    X = pd.DataFrame(...)
    Y = pd.Series(...)
    result = om.runtime.model('mymodel').score(X, Y)
    score = result.get()


Running gridsearch
------------------

*gridsearch is supported by some ML frameworks only (e.g. scikit-learn)*

.. code:: python

    X = pd.DataFrame(...)
    Y = pd.Series(...)
    result = om.runtime.model('mymodel').gridsearch(X, Y)
    score = result.get()


Tracking experiments
--------------------

Since experiments are a feature of the runtime, we can store a model
and link it to an experiment. In this case the runtime will create an
experiment context prior to performing the requested model action.

.. code:: python

    lr = LogisticRegression()
    om.models.put(lr, 'mymodel', attributes={
        'tracking': {
            'default': 'myexp',
        }})
    om.runtime.model('mymodel').score(X, Y)

Thus the runtime worker will run the following code equivalent. This is
true for all calls of the runtime (programmatic, cli or REST API).

.. code:: python

    # run time worker, in response to om.runtime.score('mymodel', X, Y)
    def omega_score(X, Y):
        model = om.models.get('mymodel')
        meta = om.models.metadata('mymodel')
        exp_name = meta.attributes['tracking']['default']
        with om.runtime.experiment(exp_name) as exp:
            exp.log_event('task_call', 'mymodel')
            result = model.score(X, Y)
            exp.log_metric('score', result)
            exp.log_artifcat(meta, 'related')
            exp.log_event('task_success', 'mymodel')


