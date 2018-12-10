What is it?
===========

*omega|ml is the production and integration platform for data science
that scales from laptop to teams to enterprise. Batteries included.*

Documentation: https://omegaml.github.io/omegaml/
Commercial License: https://omegaml.io


Features
========

*Community Edition*

omega|ml is a great choice if you want to

- get a fully integrated data science workplace within minutes [1]
- easily share models, data, jupyter notebooks and reports with your collaborators
- perform out-of-core computations on a pure-python or Apache Spark compute cluster [2]
- have a shared NoSQL database, out of the box, that behaves like a Pandas dataframe [3]
- deploy models to production with a single line of code
- serve and use models or datasets from a REST API
- use a compute cluster to train your models with no additional setup 
- scale your data science work from your laptop to team to production with no code changes
- integrate any machine learning framework or third party data science platform with a common API

[1] supporting scikit-learn, Spark MLLib out of the box, Keras and
Tensorflow available shortly. Note the Spark integration is currently only available with
the enterprise edition.
[2] using Celery, Dask Distributed or Spark
[3] leveraging MongoDB's excellent aggregation framework

In addition omega|ml provides an easy-to-use extensions API to support any kind of models,
compute cluster, database and data source.

*Enterprise Edition*

omega|ml enterprise provides security on every level and is ready made for Kubernetes
deployment. It is licensed separately for on-premise, private or hybrid cloud.
Sign up at https://omegaml.io


Get started
===========

.. code::

    $ wget https://github.com/omegaml/omegaml/blob/master/docker-compose.yml
    $ docker-compose up -d
	  
Next open your browser at http://localhost:8899 to open Jupyter Notebook. Any notebook
you create will automatically be stored within the omega|ml database, thus making it
easy to work with colleagues. The REST API is available at http://localhost:5000.


Examples
========

Get more information at https://omegaml.github.io/omegaml/

.. code::

    # transparently store Pandas Series and DataFrames or any Python object
    om.datasets.put(df, 'stats')
    om.datasets.get('stats', sales__gte=100)

    # transparently store and get models
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


FAQ
===

* How does omega|ml relate to other frameworks such as mlflow or kubeflow

    omega|ml can readily integrate with mlflow and kubeflow by using the
    extensions API. We are happy to accept any contributions or work with
    you if you have a need.

    mlflow is a generic framework to package and integrate machine learning
    models as a software asset. kubeflow provides the tooling for kuberentes
    deployment mainly for Tensorflow although extensions are planned. Neither
    package provides a standardized, out-of-the-box data science platform
    comparable to omega|ml.

* When should I choose omega|ml over other frameworks?

    You should choose omega|ml if you want to start working right now -
    omega|ml gets you from no data science to full-scale within just a
    few minutes and using a single command (we also provide a hosted
    service at https://omegaml.io).

        $ docker-compose up
        # access your notebook at http://localhost:8899

    omega|ml is a great choice if you want your team of data scientists
    and application developers to start to collaborate efficiently and leverage
    your investment in the PyData stack without being side tracked by the
    high complexity of hard to integrate third party storage and compute
    infrastructure.

    As an enterprise organization omega|ml provides a secure, managed central
    place for all your data scientist to collaborate and provide models to
    production applications. omega|ml thanks to its open scalable architecture
    works either on premise, in your private cloud or as a hybrid cloud
    leveraging all your compute and storage capabilities across data centers
    and geographies.

    However you do not need to limit yourself from using mlflow or kubeflow
    or any other framework as omega|ml by design can be readily integrated
    with almost any third party systems.

* Is it possible to use an existing data lake or datawarehouse in SQL or NoSQL
  database? How can omega|ml access data stored in an object storage or
  distributed filed system?

    Absolutely. omega|ml's extensions API provides a straight forward way
    to implement access to any storage. In particular, implement a data backend
    as follows. Please consider contributing your implementation.

        # register this class in defaults.OMEGA_STORE_BACKENDS
        class MyStorageEngine(BaseDataBackend):
            def supports(self, obj, name, **kwargs):
                return True #if obj can be stored

            def put(self, obj, name, **kwargs):
                # your code to store data
                return Metadata(...)

            def get(self, name, **kwargs):
                # your code to retrieve data
                return data

* Is it possible to use a NoSQL or SQL database completely replacing MongoDB?

    The short answer is yes, the extensions API enable any storage backend
    to be contributed transparently. However there are some caveats in terms of
    performance and scalability if you do so:

    omega|ml has been designed for high scalability from the ground up. Every
    component (API, notebooks, storage, compute, message broker) can be scaled
    independently and according to the specific needs. MongoDB follows this
    scalability approach by providing out of the box replication and sharding
    that enables data locality in every omega|ml compute node, if required.

    In summary while principally supported, this scalability feature is not
    easily achieved with every other database.

* Is omega|ml open source software? Is it free of charge?

    Yes and yes!

    omega|ml is Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License
    as per the included LICENSE file.

    omega|ml is also available as an enterprise edition with full multi-user
    security, user-separated notebooks, a notebook publishing and reporting API
    and readily packaged for Kubernetes deployments.

* I need security features and multi-user support.

    The database can easily be protected, see scripts/mongoinit.js. Then add
    `command: --auth` to the mongodb section in docker-compose.yml and
    amend the OMEGA_MONGO_URL variable. The community edition does not currently
    offer security beyond the database.

    Your fastest option to get state of the art security and multi-user features
    is to use our commercial license. It provides a multi-user security layer for
    all parts of the software, including the database, the REST API, the Jupyter
    Notebooks and all docker containers. It also provides additional deployment
    options such as Spark clusters or easy use of GPUs, deployed on Kubernetes in
    a private or hybrid cloud. We also offer additional support options in order
    to meet your specific requirements.
