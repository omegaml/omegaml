Getting started
===============

Getting User Credentials
------------------------

If you have secured MongoDB and RabbitMQ make sure to specify the
user credentials in the respective environment variables or the
omega|ml configuration file.

*Enterprise Edition*

Sign up at hub.omegaml.io to retrieve your userid and apikey. Then login as
follows. This will store your login credentials at ~/config/omegaml/config.yml
and any subsequent API call will be directed to our cloud.

.. code:: bash

    om cloud login --userid USERID --apikey APIKEY


Loading omega|ml
----------------

Start by loading omega|ml.

.. code:: python

   import omegaml as om
   
Once loaded :code:`om` provides several storage areas that are immediately usable:

* :code:`om.datasets` - storage area for Python and Pandas objects
* :code:`om.models` - storage area for models
* :code:`om.scripts` - storage area for custom modules (a.k.a. lambda modules)
* :code:`om.jobs`- storage area for jobs (ipython notebooks)

In addition, your cluster or cloud resources are available as

* :code:`om.runtime` - the omega|ml remote execution environment


Loading omega|ml from python
----------------------------

Starting up omega|ml is straight forward. In any Python program or interactive
shell just import the :code:`omegaml` module as follows:

.. code:: python

   import omegaml as om


The :code:`om` module is readily configured to work with your local omega|ml
server, or with the cloud instance configured using the :code:`om cloud login`
command.