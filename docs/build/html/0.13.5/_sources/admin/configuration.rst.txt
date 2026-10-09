Configuration
=============

.. contents::

Configuration hooks
-------------------

omega|ml is configured by constants defined in the :code:`omegaml.defaults` module.
Since this module is usually not directly changeable by the user or
administrator, the following hooks are provided:

configuration file (:code:`$HOME/.omegaml/config.yml`)
++++++++++++++++++++++++++++++++++++++++++++++++++++++

  The configuration file in Yaml format is read automatically on omega|ml
  startup, if available.

  .. note:: `Enterprise Edition`
      A user-specific configuration file can be obtained by
      any authorized user by running the :code:`python -m omegacli init` command.
      To override defaults, specify the corresponding variable in Yaml format.
 
system environment variables
++++++++++++++++++++++++++++

  To change a particular default, set the environment variable of the same
  name as the respective configuration parameter. As an example, to change
  the :code:`OMEGA_MONGO_URL` parameter, set the :code:`OMEGA_MONGO_URL` 
  environment variable. Note to change an entry in :code:`OMEGA_CELERY_CONFIG`,
  add the :code:`OMEGA_CELERY_` prefix to the environment variable name. As
  an example, to change :code:`OMEGA_CELERY[BROKER_URL]` use the env var
  :code:`OMEGA_CELERY_BROKER_URL`.

in-code update
++++++++++++++

  If you integrate omega|ml into your application, the 
  :code:`omegaml.defaults.update_from_obj` provides a direct way to update
  the defaults from any object. The object needs to support :code:`getattr` 
  on the corresponding defaults parameter.
  
The hooks are applied in the above order, that is the defaults are overriden
by configuration file, then operating system environment variables, then
constance parameters and finally your own code. Note that parameter values
specified in constance cannote be overridden by our own code except by changing
the value in the constance Django table directly.
      

Basic configuration
--------------------

.. autodata:: omegaml.defaults.OMEGA_TMP
   :annotation:
       
   Defaults to :code:`/tmp`
       
.. autodata:: omegaml.defaults.OMEGA_MONGO_URL
   :annotation:
   
   Format :code:`mongodb://user:password@host:port/database`

.. autodata:: omegaml.defaults.OMEGA_MONGO_COLLECTION


Storage configuration
---------------------

.. autodata:: omegaml.defaults.OMEGA_STORE_BACKENDS

   Dictionary of pairs :code:`{ 'kind': class }`, where
   *kind* is the Metadata.kind of the stored object, and 
   class is the python loadable name of the class that implements 
   handling of this kind. The storage backends listed in this variable are 
   automatically loaded.  

.. autodata:: omegaml.defaults.OMEGA_STORE_MIXINS

   List of storage mixin classes. The mixins listed here are automatically
   applied to each :code:`OmegaStore` instance.

   
Celery Cluster configuration
----------------------------

.. autodata:: omegaml.defaults.OMEGA_BROKER

.. autodata:: omegaml.defaults.OMEGA_RESULT_BACKEND

.. autodata:: omegaml.defaults.OMEGA_CELERY_CONFIG 

   This is used by omemgal to configure the celery application. Note
   that the configuration must be the same for both client and cluster
   worker.


Client-side configuration (constance) 
-------------------------------------

These parameters are in the admin UI at 
http://localhost:5000/admin/constance/config:

* :code:`BROKER_URL` - this is the rabbitmq broker used by the Celery cluster.
  Set as :code:`ampq://public-omegaml-hostname:port/<vhost>/`.
  Set vhost depending on your rabbitmq configuration. By default the vhost 
  is an empty string
     
* :code:`MONGO_HOST` - set as :code:`public-mongodb-hostname:port` 

* :code:`CELERY_ALWAYS_EAGER` - if this :code:`True`, all calls to the
  runtime are in fact executed locally on the calling machine. Note this
  also means that the REST API will not submit any tasks to the cluster. 