Installing omegaml
==================

.. contents::


Starting omega-ml locally
-------------------------

For a single-node installation, start the omega-ml platform as follows:

.. code::

    $ wget https://raw.githubusercontent.com/omegaml/omegaml/master/docker-compose.yml
    $ docker-compose up -d

Jupyter Notebook is immediately available at http://localhost:8899 (`omegamlisfun` to login).
Any notebook you create will automatically be stored in the integrated omega-ml database, making collaboration a breeze.
The REST API is available at http://localhost:5000.

If you already have a Jupyter or other Python environment and would like to use omega-ml's storage and
runtime environment, you can start just the required parts:

.. code::

    # start the required services
    $ docker-compose up -d mongodb rabbitmq worker

    # run omegaml from the command line
    $ om shell

    # or in your Jupyter notebook
    import omegaml as om

If you have secured MongoDB and RabbitMQ make sure to specify the user credentials
in the respective environment variables or the omega-ml configuration file, :code:`$PWD/config.yml`.

Getting User Credentials
------------------------

*Managed Service|Commercial Edition*

omega-ml is also provided as a managed service at https://omegaml.io. For on-premise
or private-cloud deployment, we provide the Commercial Edition available from the same
address.

Sign up at hub.omegaml.io to retrieve your userid and apikey. Then login as
follows. This will store your login credentials at ~/config/omegaml/config.yml
and any subsequent API call will be directed to our cloud.

.. code:: bash

    om cloud login --userid USERID --apikey APIKEY


Running omega-ml in JupyterLab, Jupyter Notebook
------------------------------------------------

omega-ml is easy to integrate with JupyterLab and Jupyter Notebook. By default
all notebooks are directly stored in the omega-ml :code:`jobs` store, so that
all team members have direct access (no sharing or uploading required).

Alternatively, any existing Jupyter installation can be used as normal. Then
omega-ml is run from the Terminal and from within your notebooks as any other
Python module (see below).

Running omega-ml from the command line
--------------------------------------

The cli command :code:`om` provides access to all of the core APIs of omega-ml:

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


Setting up R for omega-ml
-------------------------

.. code:: R

    install.packages("reticulate", repos = "https://cloud.r-project.org")
