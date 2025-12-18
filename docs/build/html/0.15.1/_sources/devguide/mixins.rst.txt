Mixins
------

Mixins come in several flavors:

* :code:`OmegaStore` mixins, enabling data pre-/post processing
* :code:`MDataFrame` mixins, enabling custom operations on lazy-evaluation dataframes
* :code:`OmegaModelProxy` mixins, enabling tasks to run on the compute cluster
* :code:`MDataFrame, MSeries` mixins, enabling custom operations on MDataFrame and MSeries objects
* :code:`ApplyContext` mixins, enabling custom operations in :code:`apply()` contexts


Storage mixins
++++++++++++++

Storage mixins typically override the :code:`get` and :code:`put` methods
to extend the functionality of backends. 

Consider users intend to store plain-text Yaml documents, which is not 
natively supported by any of the existing backends. However the default
backend supports storing Python dictionaries, so we could ask the user to 
convert the Yaml documents to Pyton dictionaries first, and then use 
:code:`om.datasets.put` to store the object. 

As a convenience to users, we provide this conversion in a storage mixin:

.. code::

   class YamlDataMixin(object):
      def put(obj, name, attributes=None, **kwargs):
          attributes = attributes or {}
          try:
             obj = yaml.loads(obj)
          except:
             pass # assume obj was some other valid type
          else:
             attributes['as_yaml'] = True
          # call the default implementation 
          return super(YamlDataMixin, self).put(obj, name, attributes=attributes, 
                                               **kwargs)
             
      def get(name, **kwargs):
          meta = self.metadata(name)
          data = super(YamlDataMixin, self).get(name, **kwargs)
          if meta.attributes.get('as_yaml'):
              data = yaml.puts(obj)   
          return data
          
To enable this mixin, call :code:`om.datasets.register_mixin`:

.. code::

   # on startup
   om.datasets.register_mixin(YamlDataMixin) 

.. note:: 

   Celery clusters require that the module providing YamlDaskMixin is available on
   both the client and the worker instance. This limitation is planned
   to be removed in future versions of omega|ml using ccbackend, which provides
   for arbitrary functions to be executed on a celery cluster. Dask Distributed
   clusters do not have this limitation.
   
Runtime mixins
++++++++++++++

Runtime mixins provide client-side extensions to `om.runtime`, specifically
to :code:`OmegaModelProxy`. OmegalModelProxy is responsible for submitting 
user-requested functions to the compute cluster. 

Consider users want to run a cross-validation procedure in some particular
way that is not supported by the default runtime. While they could use 
a job (notebook) to accomplish this, we provide a runtime mixin as a 
convenience.

.. code::

   # in crossvalidate.py
   class CrossValidationMixin(object):
       def cross_validate(modelName, Xname, Yname, *args, **kwargs):
            # get the cross validation task
            task = self.task('custom.tasks.cross_validate')
            return task.delay(modelName, Xname, Yname, *args, **kwargs)
            
   
   # in custom.tasks
   def cross_validate(modelName, Xname, Yname, *args, **kwargs):
      # get model and data
      model = om.models.get(modelName)
      xdata = om.datasets.get(Xname)
      ydata = om.datasets.get(Yname)
      # perform cross validation
      results = ...
      #   
      return results
         

To enable this mixin, add the class to :code:`om.defaults.OMEGA_RUNTIME_MIXINS`:

.. code::

  OMEGA_STORE_MIXINS = [
    'crossvalidate.CrossValidationMixin',
  ]
  
  
.. note:: 

   Celery clusters require that the custom.tasks module is available on
   both the client and the worker instance. This limitation is planned
   to be removed in future versions of omega|ml using ccbackend, which provides
   for arbitrary functions to be executed on a celery cluster. Dask Distributed
   clusters do not have this limitation.