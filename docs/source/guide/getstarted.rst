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
* :code:`om.runtime` - the omega|ml remote execution environment 


Loading omega|ml from python
---------------------------

.. code:: python

   from omegacommon.userconf import get_omega_from_apikey
   
   om = get_omega_from_apikey(username, apikey, api_url=url)
    