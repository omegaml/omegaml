Custom development
------------------

Custom development for omega|ml is available for the following extensions:

* storage backend & mixins - process and store new data types
* model backend - integrate other machine learning frameworks or custom algorithms
* runtime mixins & tasks - enable new tasks in the distributed compute-cluster

Backends provide the :code:`put,get` semantics to store and retrieve objects
where as mixins provide overrides or extensions to existing implementations.
Think of a backend as the storage engine for objects a specific data type 
(e.g. a Pandas Dataframe) while a mixin provide the pre- or post-processing 
applied to these objects on specific method calls. 

Semantics
+++++++++

Technically, storage and model backends, as well as storage mixins, extend the 
capability of :code:`OmegaStore`. Runtime mixins and tasks extend the
capability of :code:`OmegaRuntime`. :code:`MDataFrame` mixins extend the capability
of lazy-evaluation dataframes.

A data backend shall adhere to the protocol established by :code:`BaseDataBackend`. 
Similarly a model backend shall adhere to to the protocol established by 
the :code:`BaseModelBackend`. 

Both backend types support the general storage :code:`put,get` semantics to
store and retrieve objects, respectively. Model backends in addition provide
methods for specific model actions (e.g. *fit* and *predict*), following the
semantics of scikit-learn_.

.. note::

  In principle a backend need not be a subclass of either of the two base
  backends, however there is some default processing implemented in the base
  backends :code:`__init__` methods so that sub-classing is the more practical
  method.

Mixins are objects that implement arbitrary methods for their respective target.
For example, a mixin for :code:`OmegaStore` may implement a :code:`get` method,
extending the store's default implementation. Mixins are applied to their target
the same way as a subclass would be.