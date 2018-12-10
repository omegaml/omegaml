Getting started
===============

Getting User Credentials
------------------------

If you have secured MongoDB and RabbitMQ make sure to specify the
user credentials in the respective environment variables or the
omegaml configuration file.

*Enterprise Edition*

A configuration can be retrieved as follows

.. code::

  python -m omegacli init --userid test5 --apikey APIKEY --url OMEGA_URL

Loading omega|ml
----------------

Start by loading omega|ml.

.. code:: python

   import omegaml as om
   
Once loaded :code:`om` provides 3 environments that are immediately usable:

* :code:`om.datasets` - the omega|ml database for Python and Pandas objects
* :code:`om.models` - the omega|ml database for models
* :code:`om.scripts` - the omega|ml database for custom modules (a.k.a. lambda modules)
* :code:`om.runtime` - the omega|ml remote execution environment


Loading omega|ml from python
----------------------------

.. code:: python

   import omegaml as om



