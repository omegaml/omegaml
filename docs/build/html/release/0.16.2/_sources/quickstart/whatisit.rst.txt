MLOps for humans
================

*for humans* means omega-ml solves the hard parts in model deployment,
so you don't have to waste time building complex infrastructure.

.. contents::
    :depth: 3

Concepts
--------

omega-ml is built on four simple concepts:

* **OmegaStore** - a place to store and access data, models, notebooks,
  scripts in a simple, unified manner. The storage is available
  pre-configured as ``om.datasets``, ``om.models``, ``om.jobs``,
  ``om.scripts`` respectively. It provides a built-in storage using
  MongoDB but can interface with any SQL database or Blob storage,
  thus act as a virtual data layer.

* **OmegaRuntime** - a unified API to local and scalable distributed compute
  resources available to run models, scripts and notebooks. The runtime
  is available as ``om.runtime`` and via the omega-ml REST API. Independent
  of the model framework or the cloud platform, the API is always the same,
  simplifying system integration. The runtime can be run locally, in any
  cloud, in VMs, in docker or in Kubernetes.

* **Metadata** - all the metadata that describes other objects and
  the activities in the runtime. Each object is assigned a unique
  *kind* that links it to a plugin

* **Plugins** - A straight-forward plugin system ties in with all of the above.
  It is leveraging each object's *kind* to inform plugin selection and task
  delegation. Plugins make omega-ml extensible to any framework and platform.

Many of the common ML model frameworks are supported, either using a
built-in plugin by omega-ml or using any Python-based flavor provided
by mlflow. The built-in plugins are scikit-learn, keras, tensorflow
and mlflow (custom plugins are possible, e.g. for PyTorch models).


Examples
++++++++

.. code::

    # store Pandas Series and DataFrames or any Python object
    om.datasets.put(df, 'stats')
    om.datasets.get('stats', sales__gte=100)

    # store and get models
    clf = LogisticRegression()
    om.models.put(clf, 'forecast')
    clf = om.models.get('forecast')

    # run and scale models directly on the integrated Python or Spark compute cluster
    om.runtime.model('forecast').fit('stats[^sales]', 'stats[sales]')
    om.runtime.model('forecast').predict('stats')
    om.runtime.model('forecast').gridsearch(X, Y)

    # use the REST API to store and retrieve data, run predictions
    requests.put('/v1/dataset/stats', json={...})
    requests.get('/v1/dataset/stats?sales__gte=100')
    requests.put('/v1/model/forecast', json={...})

Technology stack
++++++++++++++++

omega-ml leverages a well known open-source technology stack:

* *Python* - Python provides the most versatile programming environment for
  datascience and machine learning tasks
* *MongoDB* - a scalable, high-performance and distributed database system, it
  provides straight forward storage models for any kind of data and is easy
  to run locally and in the cloud
* *RabbitMQ* - a scalable communication layer that is well supported by Python's
  Celery distributed task framework, and is also easy to run locally and in the
  cloud.

In addition, omega-ml integrates with R and any SQL database and BLOB filesystem
that provides bindings with Python. This includes MySQL, PostgreSQL, Oracle,
MS SQL Server, Snowflake, Azure BLOB, AWS S3, Google Cloud Storage, and many
others.


Key MLOps task
--------------

Deploy machine learning models in a single line of code
+++++++++++++++++++++++++++++++++++++++++++++++++++++++

Given your model, say as follows, a single line of code is all it takes
to deploy the model to the cloud and make it instantly available as a
REST API.

.. code::

        # fit your model locally
        clf = LogisticRegression()
        clf.fit(X, Y)

.. code:: python

    # deploy the model, instantly available as a REST API
    om.models.put(clf, 'mymodel')

Instantly run predictions using the built-in REST API
+++++++++++++++++++++++++++++++++++++++++++++++++++++

.. code:: bash

    # every model is instantly available as a REST API
    $ om runtime serve
    $ curl -X POST http://hostname/api/v1/model/mymodel/predict?data=X


Track model metrics
+++++++++++++++++++

.. code:: python

    # track metrics from a local experiment
    with om.runtime.experiment('myexp') as exp:
        accuracy = ...
        exp.log_metric('accuracy', accuracy)

    # track metrics from an experiment run in the cloud
    with om.runtime.experiment('myexp') as exp:
        om.runtime.model('mymodel').score('X', 'Y')

    exp.data()[['dt', 'event', 'key', 'value']]
    => tracks events, metrics across runs and steps
                               dt         event                          key                                              value
    0  2022-02-26T15:51:08.976228         start                          NaN                                                NaN
    1  2022-02-26T15:51:09.059323        system                       system  {'platform': {'system': 'Linux', 'node': 'eowy...
    2  2022-02-26T15:51:09.081621     task_call    omegaml.tasks.omega_score  {'args': ['mymodel', '_temp_37c577cdb5fe44dbb7...
    3  2022-02-26T15:51:09.190159      artifact                      related  {'name': 'related', 'data': '{"_id": {"$oid": ...
    4  2022-02-26T15:51:09.287205        metric                        score                                               0.96
    5  2022-02-26T15:51:09.305667  task_success    omegaml.tasks.omega_score  {'result': 0.96, 'task_id': '9c252aeb-6826-474...


Tasks to improve MLOps maturity
-------------------------------

Keep models versioned
+++++++++++++++++++++

Models are versioned automatically. Using tags it is easy to
access one or the other model.

.. code:: python

    om.models.revisions('mymodel')
    =>
    [('186504c5a32364513e6b5a31b651e3d1da6ba449', ''),
     ('c542d0fb4bd862541465d051b6c66d4e33df648a', ['testing']),
     ('ce2afa4cbea7bb59e7da293c90fa2179caf00ed7', ['latest', 'production'])]

    # use a specific version
    GET http://hostname/api/v1/model/mymodel#testing/predict?data=X

Easily separate dev, test and production
+++++++++++++++++++++++++++++++++++++++++

omega-ml provides easy to use namespaces.

.. code:: python

    # option 1 - store datasets and models in different paths
    om.datasets.put(df, 'dev/mydata')
    om.datasets.put(df, 'prod/mydata')
    om.models.put(clf, 'prod/mymodel')
    om.datasets.put(df, 'prod/mydata')

    # option 2 - use a separate namespace, i.e. bucket
    om_dev = om['dev']
    om.datasets.put(df, 'mydata')
    om.models.put(clf, 'mymodel')

    # option 3 - use different omega-ml instances
    om_dev = Omega(...)
    om_prod = Omega(...)

Promote objects from dev to test to production
++++++++++++++++++++++++++++++++++++++++++++++

Object promotion from one namespace to another is straight forward:

.. code:: python

    # using paths-based namespacing
    om.datasets.promote('dev/mydata', om.datasets, asname='prod/mydata')
    om.models.promote('dev/mymodel', om.datasets, asname='prod/mymodel')

    # using proper namespaces
    om_dev = om['dev']
    om_prod = om['prod']
    om_dev.datasets.promote('mydata', om_prod.datasets)
    om_dev.models.promote('mymodel', om_prod.models)

    # using different instances
    om_dev = Omega(...)
    om_prod = Omega(...)
    om_dev.datasets.promote('mydata', om_prod.datasets)
    om_dev.models.promote('mymodel', om_prod.models)

Leverage scalable cloud resources
---------------------------------

Store training data for access from local or cloud VMs
++++++++++++++++++++++++++++++++++++++++++++++++++++++

Data is accessed by any given name, using the built-in :code:`Metadata` and
a corresponding plugin. This works for any data, even on a remote URL like
http, S3, Azure Blob, Google, or in a database like Snowflake, Postgresql,
Oracle, MySQL, SQL Server.

.. code::

    # store any data
    om.datasets.put(df, 'mydataframe')
    om.datasets.put('mysql://{user}:{password}@{account}'/, 'mysqldb')
    om.datasets.put('snowflake://{user}:{password}@{account}'/, 'snowflake')
    om.datasets.put('https://example.com/data.csv' 'csvdata')

    # retrieve data
    om.datasets.get('mydataframe')
    om.datasets.get('mysqldb', sql='select * from ...')
    om.datasets.get('snowflake', sql='select * from ...')
    om.datasets.get('csvdata')
    => pd.DataFrame(...)


Train models locally and on cloud VMs
+++++++++++++++++++++++++++++++++++++

.. code:: python

    # train locally
    om.runtime.mode(local=True).model('mymodel').fit('X', 'Y')

    # train on CPU
    om.runtime.require('cpu').model('mymodel').fit('X', 'Y')

    # train on GPU
    om.runtime.require('gpu').model('mymodel').fit('X', 'Y')

Check model CPU & memory requirements
+++++++++++++++++++++++++++++++++++++

.. code:: python

    # upon deployment
    with om.runtime.experiment('myexp', provider='profiling') as exp:
        om.runtime.model('mymodel').score('X', 'Y')

    exp.data()

Scaling data pipelines
----------------------

Process larger-than memory dataframes
+++++++++++++++++++++++++++++++++++++

.. code:: python

    def transform(df):
        df['trx_week'] = df['transaction_dt'].dt.week
        df['trx_year'] = df['transaction_dt'].dt.year

    mdf = om.datasets.getl('adataframe')
    mdf.transform(df).persist('transformed-df')



Process large chunks of data using notebooks
++++++++++++++++++++++++++++++++++++++++++++

.. code:: python

    # run the myjob notebook 10 times
    results = job = om.runtime.job('myjob').map(range(10))

    #myjob is a notebook processing some chunk e.g. like this
    # -- (param = i in range)
    data = om.datasets.get('mydata', group_id=job['param'])
    results = data.groupby('customer_group').size()
    om.datasets.put(results, 'results')


Run pipelines and models in parallel
++++++++++++++++++++++++++++++++++++

.. code:: python

    # other primitives are parallel(), sequence(), mapreduce()
    with om.runtime.parallel() as crt:
        crt.job('compute-1').run()
        crt.job('compute-1').run()
        crt.job('compute-2').run()
        results = crt.run()

Production & Governance use cases
---------------------------------

Provide a REST API to notebooks, scripts, datasets and apps
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

.. code:: python

    $ om scripts put ./path/to/myscript/setup.py myscript
    => GET /api/v1/scripts/myscript/run

    $ om scripts put ./path/to/notebook.ipynb mynb
    => GET /api/v1/jobs/mynb/run

    # omega-ml commercial edition
    $ om scripts put ./path/to/myflaskapp/setup.py apps/myflaskapp
    => GET /api/v1/apphub/myflaskapp


Track model performance in production
+++++++++++++++++++++++++++++++++++++

.. code:: python

    # attach model tracking
    exp = om.runtime.experiment('myexp')
    exp.track('mymodel')

    # all prediction calls to the model's REST API will be tracked (input & output)
    exp.data()[['dt', 'event', 'key', 'value']]
    =>
    6  2021-11-26T15:51:09.458678  ...  {'args': ['mymodel', '_temp_d6fa4e0c6dc948d58b...
    7  2021-11-26T15:51:09.546344  ...  {'name': 'related', 'data': '{"_id": {"$oid": ...
    8  2021-11-26T15:51:09.624448  ...  {'result': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0..

Track all objects in built-in model, data and artefact repositories
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

omega-ml provides built-in repositories for models, data, scripts,
notebooks and streams. Each object stored is tracked by :code:`Metadata`
entry that is customizable to your needs.

.. code:: python

    om.models
    om.datasets
    om.scripts
    om.jobs
    om.streams


