Getting Started with omega|ml
=============================

omega|ml is the data science integration platform that consists of a compute cluster,
a highly scalable distributed NoSQL database and a REST API. The omega|ml Enterprise Edition
in addition provides a web dashboard, user profile management and security features.

omega|ml enables data scientists to offload all the heavy-lifting involved
with machine learning and analytics workflows, while enabling third-party apps
to use machine learning models in production the REST API.


Single node deployment
----------------------

In command line mode run

.. code::

   $ docker run mongodb
   $ pip install omegaml
   $ python -m omegaml.webapi
   $ curl http://localhost/v1/api/ping

From any Python prompt

.. code::

   [1] import pandas as pd
       import omegaml as om

       df = pd.DataFrame(...)
       om.datasets.put(df, 'stats')
       df2 = om.datasets.get('stats')
       ...

Multi node deployment
---------------------

In addition to the above also run

.. code::

   $ docker run rabbitmq
   $ celery worker --app omegaml.celeryapp -E -B --loglevel=debug

This will start a celery compute cluster that connects to the RabbitMQ instance as per default settings.



Client Configuration
--------------------

omega|ml supports two types of clients:

1. Data Science workstation - a local workstation / PC / laptop with a 
   full-scale data science setup, ready for a Data Scientist to work locally.
   When ready she will deploy data and models onto the runtime (the omega|ml 
   compute and data cluster), run models and jobs on the cluster or provide
   datasets for access by her colleagues. This configuration requires a
   local installation of omegaml, including machine learning libraries and
   client-side distribution components.
   
2. Application clients - some third-party application that access omega|ml
   datasets, models or jobs using omegaml's REST API. This configuration 
   has no specific requirements other than access to the REST API and the
   ability to send and receive JSON documents via HTTP.

.. note::

   The Data Science workstation directly connects to RabbitMQ and MongoDB.
   The Enterprise Edition comes with respective security built in, including
   user management, secured RabbitMQ channels and per-user MongoDB instances.

   If you have security needs you should subscribe to Enterprise Edition to
   avoid the cost of managing this complexity.


