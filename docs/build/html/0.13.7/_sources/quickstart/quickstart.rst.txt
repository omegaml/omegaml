Start here
==========


.. code:: python

   import omegaml as om

The :code:`om` module is readily configured to work with your local omega|ml
server, or with the cloud instance configured using the :code:`om cloud login`
command.

Once loaded :code:`om` provides several storage areas that are immediately usable:

* :code:`om.datasets` - storage area for Python and Pandas objects
* :code:`om.models` - storage area for models
* :code:`om.scripts` - storage area for custom modules (a.k.a. lambda modules)
* :code:`om.jobs`- storage area for jobs (ipython notebooks)

In addition, your cluster or cloud resources are available as

* :code:`om.runtime` - the omega|ml remote execution environment


Run in the cloud
++++++++++++++++


.. python::

Run locally
+++++++++++

Start the omega|ml server right from your laptop or virtual machine

.. code::

    $ wget https://raw.githubusercontent.com/omegaml/omegaml/master/docker-compose.yml
    $ docker-compose up -d

Jupyter Notebook is immediately available at http://localhost:8899 (`omegamlisfun` to login).
Any notebook you create will automatically be stored in the integrated omega|ml database (backed by MongoDB), making collaboration a breeze.
The REST API is available at http://localhost:5000.

Already have a Python environment (e.g. Jupyter Notebook)?
Leverage the power of omega|ml by installing as follows:

.. code::

    # assuming you have started the server as per above
    $ pip install omegaml


DataOps & MLOps for humans
--------------------------

with just a single line of code you can

- deploy machine learning models straight from Jupyter Notebook (or any other code)
- implement data pipelines quickly, without memory limitation, all from a Pandas-like API
- serve models and data from an easy to use REST API

Further, omega|ml is one of the fastest, most straight forward ways to

- leverage cloud resources to scale model training in a dynamic compute cluster
- collaborate on data science projects easily, sharing Jupyter Notebooks, datasets, models, scripts
- deploy dashboards and applications right from your Jupyter Notebook

.. info::

   * Documentation: https://omegaml.github.io/omegaml/

   * Contributions: http://bit.ly/omegaml-contribute

Examples
--------

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

