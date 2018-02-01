Public API
==========

.. autosummary::

     omegaml.datasets
     omegaml.models
     omegaml.runtime
     omegaml.jobs

     omegaml.store.base.OmegaStore
     omegaml.runtime.OmegaRuntime
     omegaml.runtime.OmegaModelProxy 
     omegaml.jobs.OmegaJobs 
     omegaml.mdataframe.MDataFrame
     omegaml.mdataframe.MGrouper
     omegaml.mdataframe.MLocIndexer


omegaml
+++++++ 

.. autodata:: omegaml.datasets
   :annotation:  - storage for data
   
.. autodata:: omegaml.models
   :annotation:  - storage for models
   
.. autodata:: omegaml.runtime
   :annotation:  - the cluster runtime API

.. autodata:: omegaml.jobs 
   :annotation:  - the lambda compute service


omegaml.store
+++++++++++++ 

.. autoclass:: omegaml.store.base.OmegaStore
   :members: list,get,getl,put,drop
   

omegaml.runtime
+++++++++++++++

.. autoclass:: omegaml.runtime.OmegaRuntime
   :members: model

.. autoclass:: omegaml.runtime.OmegaModelProxy
   :members:   

  
omegaml.jobs
++++++++++++ 

.. autoclass:: omegaml.jobs.OmegaJobs
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

