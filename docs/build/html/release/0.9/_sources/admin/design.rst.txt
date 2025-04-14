Design
======

omega runtime
-------------

The runtime implements remote execution of models and jobs. The runtime
is implemented as follows:

* :code:`OmegaRuntime` - the client API to get access to a remote model
* :code:`OmegaModelProxy` - the client API to the remote model
* :code:`runtime.tasks` - the celery tasks implementing the actual execution

A :code:`OmegaRuntime` instance is available as :code:`om.runtime`:

.. code:: python

    om = Omega()
    # get the OmegaModelProxy instance
    model = om.runtime.model('mymodel')
    # call methods on OmegaModelProxy, effecting remote task execution
    model.fit('X', 'Y')
    pred = model.predict('X')
    
Note that any method called on the :code:`model` are translated into calls
to respective celery tasks. A celery task lives in a celery worker at a remote
note. On execution a task will re-create the :code:`Omega` instance to retrieve
the *X,Y* data as well as the actual model.   

This raises the question where a task gets the configuration for recreating
the :code:`Omega` instance. The only configuration option required for a task
is the :code:`mongo_url`, which specifies the database and access credentials
where data and models are stored. As the task does not need to configure 
the runtime, it does not need any of the :code:`OmegaRuntime` configuration.  

Various options:

* **run per-user celery workers**: In this case there are 1-n celery workers
  pre-configured to run for a particular user. The Omega instance
  is configured globally as it would be when run in a client. This option
  requires a per-user deployment process where celery workers are spun up and
  task routes configured. The :code:`OmegaModelProxy` then executes tasks
  using a the user-specific celery route/queue. This is the golden option
  for the runtime as it was originally designed by this assumption. However 
  this adds a lot of complexity to the deployment process which we are not 
  yet ready to support.   

* **pass the user identification to the task**: In this case the task needs
  to be able to look up the configuration from a database. This requires the
  need for user information stored in a database accessible to Omega. The
  only database accessible to it is mongodb, which however does not have 
  user information. In fact, the database model used by Omega is on purpose
  single user (to keep it as simple as possible). Thus introducing the concept
  of user configuration into the Omega database just for remote task execution
  adds complexity that we should avoid.
  
* **pass the actual configuration**: In this case the task gets all necessary
  configuration from the client, namely the `mongo_url`. This is in line with
  how Omega itself gets the configuration. Also this does not suffer 
  from adding the complexity of user authentication to Omega. This option also
  leaves open the possibility to have user-specific deployments (as described
  above) without introducing additional overhead. The downside is that the
  mongo_url needs to be passed via network and thus is exposed through the 
  communication to the broker. The other options do not suffer from this 
  weakness. However this is a security concern best addressed by protecting 
  communication. All things considered this is the most straight-forward 
  option both in terms of additional complexity (none), future flexibility 
  and the ease of implementation. Hence this is the option we choose.
  
  
Security concerns
-----------------

* **user authentication**. Users authenticate to REST endpoints by username + 
  Apikey. Communication is protected by HTTPS.
  
* **the database** is protected by user/passwords. There is an admin database
  which uses the :code:`MONGO_ADMIN_URL`. This URL is not exposed to 
  users. The per-user databases are only exposed on a per-user basis.
  
* **communication to the database** is currently **not protected**. This needs
  to be addressed (mongo TSL support).
  
* **communication to the message broker** is currently **not protected**. This needs
  to be addressed (access protection to RabbitMQ, channel encryption (TLS) and
  possibly celery message signing).
 
* **configuration stored on the client**. REST clients only need to store username
  + apikey. Clients interfacing to the datastore via an :code:`Omega` instance
  directly only need to store the :code:`mongo_url`. Clients interfacing
  with the :code:`OmegaRuntime` need to store the broker URL +
  user credentials. Clients interfacing with a combination of the above need
  to store all credentials. Most clients will only need either mongo_url or
  username + apikey, with only few clients interfacing directly with the 
  `OmegaRuntime` (only needed for performance reasons in case of large answers
  to predictions, all other clients should use the REST endpoints).
 