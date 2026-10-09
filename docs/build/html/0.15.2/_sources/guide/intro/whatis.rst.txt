Concepts
========

omega-ml provides an out-of-the-box, cloud-native data science platform
to enable end-end development, testing and deploying of data products. The
typical buzzwords to position omega-ml are MLOps and Data Product
Operationalization.

omega-ml addresses the very questions that any (team of) data scientists, working to
build modern data products in an agile manner, has to answer at some point. To this end, the following
are "first-class citizens" in omega-ml, mapping to corresponding functionality:

.. contents::

Where to store things
+++++++++++++++++++++

* *datasets* - how to ingest, process and store data
* *models* - how to work with models, typically multiple versions thereof
* *jobs* - how to work with and eventually run notebooks on a schedule
* *scripts* - how to deploy custom functionality beyond notebooks

How to run things
+++++++++++++++++

* *runtime* - where to run model training, serve models and applications
* *streams* - how to integrate components asynchronously, as a consumer and a producer alike

How to keep track
+++++++++++++++++

* *metadata* - any object stored in omega-ml is actively tracked by its associated metadata
* *logging* - logging is as simple as, well adding messages to the log. No setup required.

How to scale
++++++++++++

* *cloud-native* - omega-ml is designed as a set of microservices, leveraging the 12factor architecture principles, and thus is fully cloud enabled. It works across clouds, private or public.
* *cloudmanager* - cloudmanager enables multi-user/multi-entity deployment of omega-ml itself as well as any other services, including your own data products (msp & commercial edition)
* *platform* - ready-made docker images and a docker-compose deployment descriptor, as well as a scalable kubernetes deployment (msp & commercial editions)

These concepts make up the very modules and APIs that omega-ml provides. For example, in
your Python code (these is an excerpt of the full capabilities):

.. code:: python

    # store a pandas dataframe
    om.datasets.put(df, 'mydataframe')

    # store a scikit learn model and fit in the cloud
    om.models.put(clf, 'mymodel')
    om.runtime.model('mymodel').fit(X, Y)

    # retrieve any size dataset and store as a dataframe
    om.datasets.read_csv('http://..../largedata.csv', 'largedata')

    # query the dataset as if it was an in-memory dataframe
    mdf = om.datasets.getl('largedata')
    mdf[mdf['city'] == 'New York']].groupby('borough').count()

The command line client works similarly:

.. code:: bash

    # store a notebook and run it in the cloud
    $ om jobs put notebook.ipynb mynotebook
    $ om runtime job mynotebook

    # run any custom script in the cloud
    $ om script put ./myscript/setup.py myscript
    $ om runtime script myscript run

The REST API provides access to models, datasets, scripts from any other
application:

.. code:: bash

    # run the model via the REST API
    $ curl https://hub.omegaml.io/api/v1/mymodel/predict?datax=mydataset






