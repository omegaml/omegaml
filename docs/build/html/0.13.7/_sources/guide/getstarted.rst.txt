Getting started
===============

omega|ml provides an out-of-the-box, cloud-native data science platform
to enable end-end development, testing and deploying of data products. The
typical buzzwords to position omega|ml are DataOps and MLOps.

Concepts
--------

omega|ml addresses the very questions that any (team of) data scientists, working to
build modern data products in an agile manner, has to answer at some point. To this end, the following
are "first-class citizens" in omega|ml, mapping to corresponding functionality:

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

* *metadata* - any object stored in omega|ml is actively tracked by its associated metadata
* *logging* - logging is as simple as, well adding messages to the log. No setup required.

How to scale
++++++++++++

* *cloud-native* - omega|ml is designed as a set of microservices, leveraging the 12factor architecture principles, and thus is fully cloud enabled. It works across clouds, private or public.
* *cloudmanager* - cloudmanager enables multi-user/multi-entity deployment of omega|ml itself as well as any other services, including your own data products (msp & enterprise edition)
* *platform* - ready-made docker images and a docker-compose deployment descriptor, as well as a scalable kubernetes deployment (msp & enterprise editions)

These concepts make up the very modules and APIs that omega|ml provides. For example, in
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


Starting omega|ml locally
-------------------------

For a single-node installation, start the omega|ml platform as follows:

.. code::

    $ wget https://raw.githubusercontent.com/omegaml/omegaml/master/docker-compose.yml
    $ docker-compose up -d

Jupyter Notebook is immediately available at http://localhost:8899 (`omegamlisfun` to login).
Any notebook you create will automatically be stored in the integrated omega|ml database, making collaboration a breeze.
The REST API is available at http://localhost:5000.

If you already have a Jupyter or other Python environment and would like to use omega|ml's storage and
runtime environment, you can start just the required parts:

.. code::

    # start the required services
    $ docker-compose up -d mongodb rabbitmq worker

    # run omegaml from the command line
    $ om shell

    # or in your Jupyter notebook
    import omegaml as om

If you have secured MongoDB and RabbitMQ make sure to specify the user credentials
in the respective environment variables or the omega|ml configuration file, :code:`$PWD/config.yml`.

Getting User Credentials
------------------------

*Managed Service|Enterprise Edition*

omega|ml is also provided as a managed service at https://omegaml.io. For on-premise
or private-cloud deployment, we provide the Enterprise Edition available from the same
address.

Sign up at hub.omegaml.io to retrieve your userid and apikey. Then login as
follows. This will store your login credentials at ~/config/omegaml/config.yml
and any subsequent API call will be directed to our cloud.

.. code:: bash

    om cloud login --userid USERID --apikey APIKEY


Running omega|ml in JupyterLab, Jupyter Notebook
------------------------------------------------

omega|ml is easy to integrate with JupyterLab and Jupyter Notebook. By default
all notebooks are directly stored in the omega|ml :code:`jobs` store, so that
all team members have direct access (no sharing or uploading required).

Alternatively, any existing Jupyter installation can be used as normal. Then
omega|ml is run from the Terminal and from within your notebooks as any other
Python module (see below).

Running omega|ml from the command line
--------------------------------------

The cli command :code:`om` provides access to all of the core APIs of omega|ml:

.. code:: bash

    $ om -h
    Usage: om <command> [<action>] [<args>...] [options]
       om (models|datasets|scripts|jobs) [<args>...] [--replace] [--csv...] [options]
       om runtime [<args>...] [--async] [--result] [--param] [options]
       om cloud [<args>...] [options]
       om shell [options]
       om help [<command>]

For example we can store and retrieve a dataset as follows:

.. code:: bash

    # load sample.csv as a DataFrame and store it as sample
    $ om datasets put sample.csv sample

    # export the pandas dataframe to a csv
    $ om datasets get sample sample.csv

Using omega|ml in python
------------------------

Starting up omega|ml is straight forward. In any Python program or interactive
shell just import the :code:`omegaml` module as follows:

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


Getting help
++++++++++++

To get help on stored objects use the per-object .help() method. This will
show the doc string of the plugin for that object. To get help on functions,
use Python's built-in help().

For example:

.. code:: python

    # per object help
    om.datasets.help('mydataset')
    om.models.help('mymodel')

.. code:: python

    help(om.datasets)
    help(om.datasets.put)
    help(om.dataests.getl('mydata'))
    help(om.runtime)





