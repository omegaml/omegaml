omega|ml - DataOps & MLOps for humans
=====================================

with just a single line of code you can

- deploy machine learning models straight from Jupyter Notebook (or any other code)
- implement data pipelines quickly, without memory limitation, all from a Pandas-like API
- serve models and data from an easy to use REST API

Further, omega|ml is the fastest way to

- scale model training on the included scalable pure-Python compute cluster, on Spark or any other cloud
- collaborate on data science projects easily, sharing Jupyter Notebooks
- deploy beautiful dashboards right from your Jupyter Notebook, using dashserve

Links
=====

* Documentation: https://omegaml.github.io/omegaml/
* Contributions: http://bit.ly/omegaml-contribute

Get started in < 5 minutes
==========================

Start the omega|ml server right from your laptop or virtual machine

.. code::

    $ wget https://raw.githubusercontent.com/omegaml/omegaml/master/docker-compose.yml
    $ docker-compose up -d

Jupyter Notebook is immediately available at http://localhost:8899 (`omegamlisfun` to login).
Any notebook you create will automatically be stored in the integrated omega|ml database, making collaboration a breeze.
The REST API is available at http://localhost:5000.

Already have a Python environment (e.g. Jupyter Notebook)?
Leverage the power of omega|ml by installing as follows:

.. code::

    # assuming you have started the server as per above
    $ pip install omega|ml


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


Use Cases
=========

omega|ml currently supports scikit-learn, Keras and Tensorflow out of the box.
Need to deploy a model from another framework? Open an issue at
https://github.com/omegaml/omegaml/issues or drop us a line at support@omegaml.io


Machine Learning Deployment
---------------------------

- deploy models to production with a single line of code
- serve and use models or datasets from a REST API


Data Science Collaboration
--------------------------

- get a fully integrated data science workplace within minutes
- easily share models, data, jupyter notebooks and reports with your collaborators

Centralized Data & Compute cluster
----------------------------------

- perform out-of-core computations on a pure-python or Apache Spark compute cluster
- have a shared NoSQL database (MongoDB), out of the box, working like a Pandas dataframe
- use a compute cluster to train your models with no additional setup

Scalability and Extensibility
-----------------------------

- scale your data science work from your laptop to team to production with no code changes
- integrate any machine learning framework or third party data science platform with a common API

Towards Data Science recently published an article on omega|ml:
https://towardsdatascience.com/omega-ml-deploying-data-machine-learning-pipelines-the-easy-way-a3d281569666

In addition omega|ml provides an easy-to-use extensions API to support any kind of models,
compute cluster, database and data source.

*Enterprise Edition*

https://omegaml.io

omega|ml Enterprise Edition provides security on every level and is ready made for Kubernetes
deployment. It is licensed separately for on-premise, private or hybrid cloud.
Sign up at https://omegaml.io
