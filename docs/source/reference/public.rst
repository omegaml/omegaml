Public API
==========

omegaml
-------

.. autodata:: omegaml.datasets
   :annotation:  - storage for data
   
.. autodata:: omegaml.models
   :annotation:  - storage for models
   
.. autodata:: omegaml.runtime
   :annotation:  - the cluster runtime API


omegaml.store
-------------

.. autoclass:: omegaml.store.base.OmegaStore
   :members: list,get,put,drop
   

omegaml.runtime
---------------

.. autoclass:: omegaml.OmegaRuntime
   :members: model

.. autoclass:: omegaml.OmegaModelProxy
   :members:   


omegaml.jobs
------------

.. autoclass:: omegaml.jobs.OmegaJobs
   :members: run, run_notebook, schedule
