Key features
------------

.. contents::

Ready to be productive
++++++++++++++++++++++

It is an integrated, Python-native yet open data science platform with

* end-2-end features for collaboration, development and deployment,
* based on well-known open source components to make integration & scaling easy
* omega|ml does not change the way you work, yet it enables the hard parts -- usually from a single line of code.

For example,

.. code:: python

    # store data, anyone on the team can retrieve it immediately
    # -- Joe stores the data
    om.datasets.put(df, 'mydata')
    # -- Sally retrieves it
    df = om.datasets.get('mydata')

    # run a notebook in the cloud
    om.runtime.job('mynotebook').run()

    # share a model for evaluation by someone else on the team
    # -- Sally stores the model
    om.models.put(clf, 'mymodel')
    # -- Joe gets it back
    clf = om.models.get('mymodel')

    # fit the model on a gpu, in the cloud
    om.runtime.require('gpu').model('mymodel').fit()

    # in parallel, process a larger-than memory dataframe with native Pandas
    def process(df):
        # pandas code
        ...

    mdf = om.datasets.getl('verylarge')
    mdf.transform(process).persist('large-transformed')


Start small, scale easily
+++++++++++++++++++++++++

omega|ml's philosophy is to provide both novice and expert users a fast start while enabling them
to scale easily and at any time. It does so by providing a ready-made environment
that works the same from laptop to cloud, as well as across clouds -- without code change.

For example running a model locally, in the cloud or on a gpu cluster literally is the
same command (with one parameter specifying the environment):

.. code:: bash

    # run in the cloud (regmodel is a scikit-learn model, sample is a Pandas dataframe)
    $ om runtime model regmodel fit sample[x] sample[y]

    # run on a gpu cluster
    $ om runtime model regmodel fit sample[x] sample[y] --require gpu

    # run locally
    $ om runtime model regmodel fit sample[x] sample[y] --local

    # all commands return a Metadata entry and store a new version of the regmodel
    <Metadata: Metadata(name=regmodel,bucket=omegaml,prefix=models/,kind=sklearn.joblib,created=2020-09-09 23:27:29.676000)>

No-hassle data access, storage & processing
+++++++++++++++++++++++++++++++++++++++++++

Data scientists spend a large part of their time accessing and processing data, and
as any team will confirm, setting up data storage is a major effort any organization. Yet it is not
a core skill of data science teams, nor should it be. To this end, and because data ingestion,
processing and access is at the core of any data product, omega|ml provides
an integrated, scalable analytics store with an integrated cloud-native filesystem (leveraging MongoDB's
open source edition).

As part of its *datasets* API it also integrates with any third-party database that provides a Python or REST API.
Today, omega|ml includes support for MongoDB, MySQL, PostgreSQL, Oracle and any other DBMS supported by SQLAlchemy. Other
DBMS or filesystems can be integrated using custom plugins.

Instant deployment
++++++++++++++++++

Datasets, models and pipelines are instantly deployed and promoted from one environment to another.
Instantly means "in seconds". There are no build scripts to run, no handover to DevOps, no docker images
to update and deploy.

For example, deploying a model so that a client application can access it from the REST API is a single
statement:

.. code:: python

    # assume regmodel is a trained scikit-learn model (can be any other model)
    om.models.put(regmodel, 'mymodel')

This operation typically completes in a fraction of a second. Instantly there is REST API that other
systems can access:

.. code:: bash

    $ curl https://hub.omegaml.io/api/v1/model/mymodel/predict --data {...}

Models as data, not code
++++++++++++++++++++++++

A machine learning model essentially consists of a given algorithm + weights + hyper parameters.
Weights and parameters are data, not code, while the algorithm of any particular model is a reference
to a static library. From this perspective, treating models as data is a more natural fit than creating
packaging semantics around weights + hyper parameters.

Treating models as data instead of code enables many useful scenarios, all of which are supported
by omega|ml out of the box. In particular, in any collaborate environment and even more importantly
in productive ML systems we want to:

* share and deploy new models immediately
* re-train models automatically, in production
* capture run-time model inputs for later use in quality assurance
* run multiple model versions (rendezvous architecture)

Read more about this in http://bit.ly/omegaml-models-as-data

Multi-environment
+++++++++++++++++

omega|ml integrates facilities for both logical and physical segregation of environments. Promotion
between environments is, again, a single line of code.

* Logical segregation means namespacing different parts of the system. For example each project
  could be using a different namespace; the development environment could be one namespace, the
  production environment another. In logical segregation all resources are shared, yet access
  to each environment is by a different key. In omega|ml a namespace is called a bucket.

* Physical segregation means to use different environments where each environment provides
  dedicated resources. omega|ml supports this by its 12-factor architecture style, meaning that
  every resource is attached from a configuration setting. To run in different environments, a
  different configuration suffices.

Promoting objects from one environment to another, whether logically or physically segregated works like this:

.. code:: python

    om_dev  = ... # development environment
    om_prod = ... # production environemnt

    om_dev.datasets.promote('mydataset', om_prod.datasets)
    om_dev.models.promote('mymodel', om_dev.models)

Straight-forward to integrate & operate
+++++++++++++++++++++++++++++++++++++++

One key feature is that omega|ml integrates easily with well-known components in the PyData and Python fullstack.
At the core designed as an open framework, it works with your existing
data science frameworks like Pandas, Numpy, scikit-learn, Tensorflow, Keras
and PyTorch. Other frameworks can be supported by adding a plugin, called a backend.
In fact, most of omega|ml is built from plugins.

.. note::

    * Frameworks supported out of the box: all of the PyData stack like Pandas, Numpy,
      scipy, scikit-learn, Tensorflow, Pytorch, Jupyter Lab & Jupyter Notebook. Other libraries
      and frameworks are easy to integrate as plugins.
    * Components at its core: Python, Flask, Celery, MongoDB and RabbitMQ.
    * Cloud deployments: somega|ml is ready-made to work with Docker and Kubernetes, however can also be run
      on "bare metal" easily.

    The application of well known backend components like MongoDB and RabbitMQ is both a unique feature
    and an advantage over platforms that introduce new, often complex technologies. This means omega|ml is easy
    to integrate and operate because its core components are already known, battle tested -- and
    skills are widly available. In contrast, the same is not true for many other platforms, which typically introduce new, highly specialised
    technologies (e.g. Spark, Kafka, Flink).

    At the same time omega|ml is designed from the ground up as an open framework
    that provides a unified API to any third-party database, data science framework or cloud platform. This means that even otherwise more complex
    backends can be effectively provided to data product teams so they can move fast, while specialist
    DevOps providers can concentrate on efficient platform operations.

Built on simple core concepts
++++++++++++++++++++++++++++++

All of the above features are really based on just four core concepts:

* *OmegaStore*  - A metadata-driven storage model, providing object and filesystem-storage, enabling storing any object (models, datasets, pipelines, streams, logs, metadata etc.)
* *OmegaRuntime* - A task-based runtime model that does not assume any particular backend
* *Metadata* - Keeping track of every object, each object is assigned a unique type identifier (aka *kind*)
* *Plugins* - A straight-forward plugin system ties in with all of the above, leveraging each object's
  *kind*, stored in Metadata, to inform plugin selection and task delegation

These four concepts are applied to provide the full scope of the features described above. Most of omega|ml is based on
plugins that make use of
