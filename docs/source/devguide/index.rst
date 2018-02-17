Development Guide
=================

Custom development for omegaml is available for the following extensions:

* storage backend & mixins - process and store new data types
* model backend - integrate other machine learning frameworks or custom algorithms
* runtime mixins & tasks - enable new tasks in the distributed compute-cluster

Backends provide the :code:`put,get` semantics to store and retrieve objects
where as mixins provide overrides or extensions to existing implementations.
Think of a backend as the storage engine for objects a specific data type 
(e.g. a Pandas Dataframe) while a mixin provide the pre- or post-processing 
applied to these objects on specific method calls. 

Basics
------  

Technically, storage and model backends, as well as storage mixins, extend the 
capability of :code:`OmegaStore`. Runtime mixins and tasks extend the
capability of :code:`OmegaRuntime`.

A data backend shall adhere to the protocol established by :code:`BaseDataBackend`. 
Similarly a model backend shall adhere to to the protocol established by 
the :code:`BaseModelBackend`. 

Both backend types support the general storage :code:`put,get` semantics to
store and retrieve objects, respectively. Model backends in addition provide
methods for specific model actions (e.g. *fit* and *predict*), following the
semantics of scikit-learn_.

Metadata
++++++++

Before we go in to the technical details of each type of backend we need
to understand how omegaml keeps track of the objects it stores. For every
object stored in omegaml, :code:`OmegaStore` creates a `Metadata` object.

A :code:`Metadata` object is returned to the caller on every call to 
:code:`om.datasets.put`, :code:`om.models.put` and :code:`om.jobs.put`:

.. code::

  om.datasets.put(df, 'foo')
  => 
  <Metadata: Metadata(bucket=omegaml,id=59ce7013de39d13d02419bb1,
  uri=None,s3file={},kind=pandas.dfrows,prefix=data/,attributes={},
  kind_meta={'columns': [['_idx_0', '_idx_0'], ['x', 'x'], ['y', 'y']], 
  'idx_meta': {'names': [None]}},gridfile=<GridFSProxy: (no file)>,
  collection=omegaml.data_.sample.datastore,objid=None,
  created=2017-09-29 16:08:51.042000,name=sample)>
 
Metadata in combination with customizable backends are a key component 
to omegaml's flexibility as it enables the storage of arbitrary objects. 

Each object is assigned a :code:`Metadata.kind`, a unique string that 
identifies the object type. On retrieving (:code:`get`) it is this value 
that provides the lookup for the specific backend implementation able to handle
this object type. On storing an object (:code:`put`) it is the backend's
:code:`supports` method    

Storage backend
---------------   

.. _scikit-learn: 

A storage backend can support additional data types for the 
:code`datasets,models,jobs` stores. All stores share the same backends as 
they use the same implementation throughout. There are two types of backends:
data backends and model backends. 

.. note::

  In principle a backend need not be a subclass of either of the two base
  backends, however there is some default processing implemented in the base
  backends :code:`__init__` methods so that sub-classing is the more practical
  method.
  
Data backend
++++++++++++

A data backend 
  





