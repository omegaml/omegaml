Public API
==========

Python API (overview)
---------------------

.. autosummary::
     
     omegaml.datasets 
     omegaml.models
     omegaml.runtime
     omegaml.jobs
     omegaml.scripts

     omegaml.store.base.OmegaStore
     omegaml.runtime.OmegaRuntime
     omegaml.runtime.OmegaRuntimeDask
     omegaml.runtime.OmegaModelProxy
     omegaml.runtime.OmegaJobProxy
     omegaml.runtime.OmegaScriptsProxy
     omegaml.jobs.OmegaJobs

     omegaml.mdataframe.MDataFrame
     omegaml.mdataframe.MGrouper
     omegaml.mdataframe.MLocIndexer
     omegaml.mdataframe.MPosIndexer

REST API (overview)
-------------------

.. autosummary::

     omegaweb.resources.dataset 
     omegaweb.resources.model
     omegaweb.resources.jobs
     omegaweb.resources.scripts

Python API
----------

omega|ml
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
   :noindex:
   

omegaml.runtime
+++++++++++++++

.. autoclass:: omegaml.runtime.OmegaRuntime
   :members: model
   
.. autoclass:: omegaml.runtime.OmegaRuntimeDask
   :members: model

.. autoclass:: omegaml.runtime.OmegaModelProxy
   :members:   
  
.. autoclass:: omegaml.runtime.OmegaJobProxy
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

.. autoclass:: omegaml.mdataframe.MPosIndexer
   :special-members: __getitem__

.. autoclass:: omegaml.mixins.mdf.ApplyContext

.. autoclass:: omegaml.mixins.mdf.ApplyArithmetics
   :special-members: __mul__, __add__,

.. autoclass:: omegaml.mixins.mdf.ApplyDateTime

.. autoclass:: omegaml.mixins.mdf.ApplyString

.. autoclass:: omegaml.mixins.mdf.ApplyAccumulators


REST API
--------

  
omegaweb.resources.dataset
++++++++++++++++++++++++++
 
.. autoclass:: omegaweb.resources.dataset.DatasetResource
   :members:
   :exclude-members: restore_filter

omegaweb.resources.model
++++++++++++++++++++++++

   
.. autoclass:: omegaweb.resources.model.ModelResource
   :members:
 
omegaweb.resources.jobs
+++++++++++++++++++++++  

.. autoclass:: omegaweb.resources.jobs.JobResource
   :members:

omegaweb.resources.scripts
++++++++++++++++++++++++++

.. autoclass:: omegaweb.resources.scripts.ScriptResource
   :members:
              
              
              
              
             
                
                
                
                
                
                 
                  
                  
                  
                  
                   
                   

