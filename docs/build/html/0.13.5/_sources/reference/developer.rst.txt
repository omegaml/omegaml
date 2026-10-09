Developer API
=============

omega|ml
--------

.. automodule:: omegaml
   :members: Omega


omegaml.store
-------------

.. automodule:: omegaml.store.base

.. autoclass:: omegaml.store.base.OmegaStore
   
   
omegaml.backends
----------------

.. autoclass:: omegaml.backends.basedata.BaseDataBackend 

.. autoclass:: omegaml.backends.basemodel.BaseModelBackend

.. autoclass:: omegaml.documents.Metadata


omegaml.mixins
-----------------------

.. autoclass:: omegaml.mixins.store.ProjectedMixin
.. autoclass:: omegaml.mixins.mdf.FilterOpsMixin
.. autoclass:: omegaml.mixins.mdf.ApplyMixin
.. autoclass:: omegaml.mixins.mdf.ApplyArithmetics
   :special-members: __mul__
   :private-members: __mul__

.. autoclass:: omegaml.mixins.mdf.ApplyDateTime
.. autoclass:: omegaml.mixins.mdf.ApplyString
.. autoclass:: omegaml.mixins.mdf.ApplyAccumulators


omegaml.runtimes
----------------

.. autoclass:: omegaml.runtimes.OmegaRuntime

.. autoclass:: omegaml.runtimes.OmegaModelProxy

.. autoclass:: omegaml.runtimes.OmegaJobProxy

.. autoclass:: omegaml.runtimes.OmegaRuntimeDask


omegaml.documents
-----------------

.. autoclass:: omegaml.documents.Metadata


omegaml.jobs
------------

.. autoclass:: omegaml.notebook.jobs.OmegaJobs


omegajobs
---------

.. autoclass:: omegaml.notebook.omegacontentsmgr.OmegaStoreContentsManager


