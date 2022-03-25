Architecture
============

.. contents::

Why omega-ml
------------

A typical data science workflow consists of the following core steps:

1. acquire data & store for subsequent processes
2. clean data & publish for uses
3. train & evaluate models
4. publish models & reports
5. execute prediction using previously trained models

In any production scenario, each step requires a scalable storage to store raw and cleaned data, models and
APIs to execute models. You will also need a compute cluster that is easy to access and provides all the
required packages. Engineering such a system from scratch is hard, takes considerable time and skills. omega-ml
provides all of this in an integrated, scalable fashion.

omega-ml provides

* the central storage for data and models, using MongoDB as the highly-scalable storage provider
* a client API to out-of-core data processing that follows Pandas semantics
* a client API to models that follows scikit-learn semantics, integrating scikit-learn and Apache Spark models
* an integrated compute cluster runtime to train and execute models, as well as to execute arbitrary scripts and
  automatically publish reports
* a sophisticated REST API to data, models, scripts and runtime
* a user interface to access information on all of the above

Extensibility
-------------

With the exception of the REST API, all of the above are easily extensible using mixins.

In addition, omemgal provides interfaces to existing compute clusters like Anaconda's Distributed and
Apache Spark. omega-ml also provides an extensible framework to add custom backends and compute clusters
through a common API.

Thanks to extensibility at the core of the architecture, omega-ml can easily accommodate any third-party storage
or machine learning backend, or add new types of operations on data and models.

How omega-ml works
------------------

* data is stored via the :code:`datasets.put` API. :code:`datasets.put`
  supports native Python objects like dicts and lists, Pandas DataFrames
  and Series, numpy arrays as well as externally stored files that are
  accessible through http, ftp or stored on cloud services like Amazon's s3.
  Other datatypes can be easily added by a custom data backend.

* machine learning models are stored via the :code:`models.put` API.
  :code:`models.put` supports scikit-learn and Spark mllib models. Other
  machine learning frameworks can be easily added by a custom model backend.

* jobs (custom python scripts in the form of Jupyter notebooks) are stored
  via the :code:`jobs.put` API.

* the runtime cluster and any other authorized user can access the data
  models and jobs through the :code:`datasets.get`, :code:`models.get` and
  :code:`jobs.get` methods, respectively. Using this common API any compute
  job e.g. to train a model can directly access the relevant data without
  the need to transfer the data to the worker instance first.


omega-ml is composed of the following main components:

Core components
---------------

The core components provide the storage for data and models. Models can
be trained locally and stored in the cluster for prediction via the REST
API.

* :code:`Omega` - the main API and programming interface to omega-ml
* :code:`OmegaStore` - the storage for data and models
* :code:`OmegaRuntime` - the celery runtime cluster to train and execute models and jobs


Commercial Edition
------------------

The omega-ml Commercial Edition provides a fully integrated, commercial-scale data science platform as a service.
It is the best match for a multi-user environment with security features and an extended set of functionality.

* :code:`security features` - security features covering all components (REST API, MongoDB, RabbitMQ etc.)
* :code:`omegaweb` - a secured REST API, web interface and dashboard
* :code:`omegaops` - cloud manager operations
* :code:`omegajobs` - JupyterHub with per-user Notebooks
* :code:`apphub` - application hub to provision and host data applications


Third-party dependencies
------------------------

.. _MongoDB: https://www.mongodb.com/
.. _RabbitMQ: https://www.rabbitmq.com/
.. _Celery: http://www.celeryproject.org/
.. _MySQL: https://dev.mysql.com/

omega-ml depends on the following third-party products (all open source):

* MongoDB_ - the highly scalable NoSQL database, ideal for data science workloads
* RabbitMQ_ - the most-widely used open source message broker
* Celery_ - the efficient and highly-throughput Distributed Task Queue for Python applications
* MySQL_ - the world's most popular open source database, backed by Oracle

Note that omegaml's license does not include the above products. However,
omega-ml provides the required docker build instructions to download,
install and configure these applications for use with omegaml.

A number of smaller third-party components in the Python ecosystem are used
in omegaml. Refer to the LICENSES file for details.
