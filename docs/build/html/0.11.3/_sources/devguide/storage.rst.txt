Storage backends
----------------  

.. _scikit-learn: http://scikit-learn.org 

A storage backend can support additional data types for the 
:code:`datasets,models,jobs` stores. All stores share the same backends as 
they use the same implementation throughout. There are two types of backends:
data backends and model backends.

All storage backends are initialized to know their respective data and model
stores as :code:`self.data_store` and `self.model_store`, respectively.

Accessing MongoDB
+++++++++++++++++       

:code:`OmegaStore`, accessible from a backend implementation as 
:code:`self.data_store`, provides several methods and properties to interact 
with mongodb.  

* :code:`self.data_store.metadata(name)` - return the meta data object
  for the given object

* :code:`self.data_store.collection(name)` - return the mongodb Collection
  instance for the given object
  
* :code:`self.data_store.fs` (property) - return the mongodb GridFS instance

* :code:`self.data_store.mongodb` (property) - return the mongodb Database
  instance
  
.. warning::

   A custom backend shall not use any other means to access mongodb as doing
   so may cause unexpected side-effects.
   
Generating unique names
+++++++++++++++++++++++

To generate a unique name for an object that is compatible with MongoDB
collection and GridFS naming rules use the :code:`self.data_store.object_store_key` 
method.

.. code:

  # some class FooDataBackend(BaseDataBackend):
  def put(self, obj, name, **kwargs):
    name = self.data_store.object_store_key(name, ext):
    # store using the name
    ... 
    return ...
     
.. note::

   The :code:`.collection` method already uses :code:`object_store_key()`
   to set the collection name for a given object.     
  
Choosing MongoDB GridFS or collection
+++++++++++++++++++++++++++++++++++++

.. _MongoDB documents: http://api.mongodb.com/python/current/tutorial.html#documents 
.. _MongoDB type mapping: http://api.mongodb.com/python/current/api/bson/index.html?highlight=data%20type

If the data type of an object is some form of iterable a MongoDB collection
may be well suited to store the data.

.. code::
  
   # some class FooDataBackend(BaseDataBackend):
   def put(self, obj, name, **kwargs):
      # store obj in collection
      collection = self.data_store.collection(name)
      collection.insert_many([dict(item) for item in obj])
      # create meta data
      meta = self.data_store.make_metadata(name, 'foo.rows')
      meta.collection = collection
      return meta.save()
      
.. note::

  The :code:`dict(item)` call may or may not be necessary. In general for
  MongoDB to be able to store the object, it must be BSON serializable. See
  the tutorial on `MongoDB documents` and `MongoDB type mapping`_.

If the data type is of binary form, a GridFS file may be the better choice.

.. code::

   # some class FooDataBackend(BaseDataBackend):
   def put(self, obj, name, **kwargs):
      # store obj in gridfs
      filename = self.data_store.object_store_key(name, 'foo')
      buf = BytesIO(obj)
      fileid = self.data_store.fs.put(buf, filename=filename)
      # create meta data
      meta = self.data_store.make_metadata(name, 'foo.file')
      meta.gridfile = GridFSProxy(grid_id=fileid)
      return meta.save()
      
.. note::
  
  The above code snippets only show the :code:`put` method. Implement the
  :code:`get` method to retrieve the object from the object's collection or 
  GridFS file, as indicated by :code:`meta.kind`. It is the responsibility of
  the backend to apply whatever data conversions are necessary, i.e. 
  :code:`OmegaStore` does not implement any automatic conversions.
  

Storing data outside MongoDB
++++++++++++++++++++++++++++

:code:`OmegaStore` is oblivious to the storage location of the actual data of 
an object, as long as there is a backend that handles storing (put) and 
retrieval (get). In other words OmegaStore in combination with a backend
implementation can deal with arbitrary data and storage methods. 

For data stored in MongoDB, :code:`Metadata.collection` and :code:`Metadata.gridfile` provide
the necessary pointers. For data stored outside mongodb, :code:`Metadata.uri` provides
an arbitrary URI that a backend can set (on :code:`put`) and use for retrieval
(on :code:`get`).

.. code:: 

   # some class FooDataBackend(BaseDataBackend):
   def put(self, obj, name, **kwargs):
      # store obj in some external file system
      filename = self.date_store.object_store_key(name, 'foo')
      buf = BytesIO(obj)
      # get instance of external file system and create file URI
      # note the URI can be anything as long as your get method knows how
      # to dereference
      foofs = ... 
      fileid = foofs.put(obj, filename=filename)
      uri = 'foofs://{}'.format(fileid)
      # create meta data
      meta = self.data_store.make_metadata(name, 'foo.file')
      meta.uri = uri 
      return meta.save()
      
   def get(self, name, **kwargs):
      # get metadata and URI
      meta = self.data_store.metadata(name)
      uri = meta.uri
      # get object back using some service that understands this uri
      service = ... 
      obj = service.get(uri)
      return obj
    
    
Data backend
++++++++++++

A data backend minimally provides the :code:`put` and :code:`get` methods:

.. code::

   # some class FooDataBackend(BaseDataBackend):
   def put(self, obj, name, **kwargs):
       # code to store the object
       ...
       # create or update the metadata object
       meta = self.data_store.metadata(name)
       if meta is None:
          meta = self.data_store.make_metadata(name, kind)
       # always save the Metadata instance before returning
       return meta.save()

   def get(self, name, **kwargs):
       # code to retrieve the object 
       obj = ...
       return obj
  

Model backend
+++++++++++++

.. _model persistency: http://scikit-learn.org/stable/modules/model_persistence.html

Model backends store and retrieve instances of models (in the scikit-learn 
sense of `model persistency`_). In addition, they act as the model proxy used
by :code:`OmegaRuntime` to perform arbitrary actions on an saved model using
named data objects.

The actions expected to be available minimally to :code:`OmegaRuntime` 
on a saved model are as follows. Note that these methods accept the *modelname*,
*XName*, and *Yname* parameters, which must all reference existing objects
in the `om.models` and `om.datasets` stores, respectively. 

.. note:: 

   Technically, these methods are called from a worker in the compute cluster
   *without* prior loading of the model nor the data. The worker uses
   `om.models.get_backend()` to retrieve the model's backend, then calls
   the requested method. Thus it is the responsibility of the backend to 
   retrieve the model and any data required.

.. currentmodule:: omegaml.backends.basemodel

.. automethod:: BaseModelBackend.fit
.. automethod:: BaseModelBackend.predict
.. automethod:: BaseModelBackend.transform

This is in addition to the :code:`put` and :code:`get` methods required by
any storage backend. 

Ideally and for user convenience, more methods should be supported, 
see the reference on :code:`BaseModelBackend`. Methods that are not supported
will raise the :code:`NotImplemented` exception.

