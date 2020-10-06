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

     omegaml.store.base.OmegaStore
     omegaml.runtimes.OmegaRuntime
     omegaml.runtimes.OmegaRuntimeDask
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

omega|ml
++++++++

.. autodata:: omegaml.datasets
   :annotation:  - storage for data

.. autodata:: omegaml.models
   :annotation:  - storage for models

.. autodata:: omegaml.runtimes
   :annotation:  - the cluster runtime API

.. autodata:: omegaml.notebook.jobs
   :annotation:  - the lambda compute service


omegaml.store
+++++++++++++

.. autoclass:: omegaml.store.base.OmegaStore
   :members: list,get,getl,put,drop
   :noindex:


omegaml.runtimes
++++++++++++++++

.. autoclass:: omegaml.runtimes.OmegaRuntime
   :members: model

.. autoclass:: omegaml.runtimes.OmegaRuntimeDask
   :members: model

.. autoclass:: omegaml.runtimes.OmegaModelProxy
   :members:

.. autoclass:: omegaml.runtimes.OmegaJobProxy
   :members:


omegaml.jobs
++++++++++++

.. autoclass:: omegaml.notebook.jobs.OmegaJobs
   :members: run, run_notebook, schedule


omegaml.mdataframe
++++++++++++++++++

.. autoclass:: omegaml.mdataframe.MDataFrame
   :members: groupby, inspect, __len__, value, sort, head, skip, merge, query, query_inplace, create_index, loc
   :special-members: __len__

.. autoclass:: omegaml.mdataframe.MSeries
   :inherited-members: groupby, inspect, value, sort, head, skip, merge, query, query_inplace, create_index, loc
   :special-members: __len__


.. autoclass:: omegaml.mdataframe.MGrouper
   :members: agg, aggregate, count

.. autoclass:: omegaml.mdataframe.MLocIndexer
   :special-members: __getitem__

.. autoclass:: omegaml.mdataframe.MPosIndexer
   :special-members: __getitem__

.. autoclass:: omegaml.mixins.mdf.ApplyContext

.. autoclass:: omegaml.mixins.mdf.ApplyArithmetics
   :special-members: __mul__, __add__,

.. autoclass:: omegaml.mixins.mdf.ApplyDateTime

.. autoclass:: omegaml.mixins.mdf.ApplyString

.. autoclass:: omegaml.mixins.mdf.ApplyAccumulators


Backends:

.. autoclass:: omegaml.backends.sqlalchemy.SQLAlchemyBackend
