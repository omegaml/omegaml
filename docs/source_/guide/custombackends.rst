Implementing a Custom Backend
==============================

omega|ml currently provides two types of extensible backends:

1. :code:`CustomDataBackend` - to store and retrieve data objects
2. :code:`CustomModelBackend` - to store, retrieve and execute model objects
   (execute = fit, predict, ...)
   
To implement your own data backend, implement all methods in each backend. 
Once implemented, use :code:`OmegaStore.register_backend` to have the omegaml's
storage layer work with your backend implementation. All storage methods are
then supported out of the box, mainly :code:`put,get,list,drop`. 

.. note::

  Your backend's respective :code:`put, put_model` methods need to
  return a saved :code:`Metadata` object. Create a metadata
  object using :code:`OmegaStore.make_metadata()`.