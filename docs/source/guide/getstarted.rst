Getting started
===============

Setting up
----------

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
---------------------------

.. code:: python

   import omegaml as om
   om.setup(username, apikey, api_url=url)

Typically, the URL will be set by your default configuration. 
    