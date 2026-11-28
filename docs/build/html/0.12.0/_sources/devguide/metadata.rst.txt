Metadata
++++++++

Before we go in to the technical details of each type of backend we need
to understand how omega|ml keeps track of the objects it stores. For every
object stored in omegaml, :code:`OmegaStore` creates a `Metadata` object.

A :code:`Metadata` object is returned to the caller on every call to 
:code:`om.datasets.put`, :code:`om.models.put` and :code:`om.jobs.put`:

.. code::

  om.datasets.put(df, 'sample')
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
that provides the lookup in :code:`defaults.OMEGA_STORE_BACKENDS` for 
the specific backend implementation to handle this object type.

.. code::

    # code snippet from OmegaStore 
    def get_backend(...):
      ...
      backend_cls = load_class(self.defaults.OMEGA_STORE_BACKENDS.get(meta.kind))
      if backend_cls:
          backend = backend_cls(**kwargs)
          return backend
      ... 


On storing an object (:code:`put`) it is the backend's
:code:`supports` method that identifies whether the backend can deal with
the object type. 

.. code::

   # in some class FooDataBackend(BaseDataBackend) or FooModelBackend(BaseModelBackend)
   def supports(self, obj, name, **kwargs):
      # check if obj with given name and kwargs is supported
      check = ...
      return check    