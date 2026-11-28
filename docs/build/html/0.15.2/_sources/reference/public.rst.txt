Public API
==========

Python API (overview)
---------------------

.. autosummary::

     omegaml.datasets
     omegaml.models
     omegaml.runtimes
     omegaml.jobs
     omegaml.scripts
     omegaml.streams
     omegaml.logger

     omegaml.store.base.OmegaStore
     omegaml.runtimes.OmegaRuntime
     omegaml.runtimes.OmegaModelProxy
     omegaml.runtimes.OmegaJobProxy
     omegaml.notebook.jobs.OmegaJobs

     omegaml.mdataframe.MDataFrame
     omegaml.mdataframe.MGrouper
     omegaml.mdataframe.MLocIndexer
     omegaml.mdataframe.MPosIndexer

     omegaml.backends.sqlalchemy.SQLAlchemyBackend

Python API
----------

.. autodata:: omegaml.models

.. autodata:: omegaml.runtimes
   :annotation:  - the cluster runtime API

.. autodata:: omegaml.notebook.jobs
   :annotation:  - the lambda compute service


omegaml.store
+++++++++++++

.. autoclass:: omegaml.store.base.OmegaStore
   :members: list,get,getl,put,drop
   :noindex:





omegaml.jobs
++++++++++++

.. autoclass:: omegaml.notebook.jobs.OmegaJobs
   :members: run, run_notebook, schedule


