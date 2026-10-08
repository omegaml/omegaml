Getting Started with OmegaML
============================

OmegaML is an API service that consists of a worker connected to a
broker (rabbitmq) and a mongo database. It enables an end user do
offload all the heavylifting involved with running analytics.

Installation
------------

OmegaML can be easily installed with pip using

``sudo pip install omegaml``

Configuration
-------------

OmegaML takes much of its configuration parameters from
``omegaml.defaults``. For any customization all you need to do is export
an environment variable with the same name. For e.g, say if you want to
change the mongo url to some destination other than the default on your
shell all you need to do is

::

    # export OMEGA_MONGO_URL='user@host:port/db

and omegaml reconfigure itself. See ``omegaml.defaults`` for more.

Using OmegaML on private Spark Cluters
--------------------------------------

OmegaML can be installed on any machine of your preference following below steps:

* install omegaml using pip
* set env variables for mongodb and rabbitmq
* start celery worker
* import omegaml on start of pyspark