Design
======

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


Security concerns
-----------------

Note that the open source `omega|ml Core` does not implement any security by default.
The omega|ml Enterprise Edition however addresses all security concerns:

* **user authentication**. Users authenticate to REST endpoints by username +
  Apikey. Communication is protected by HTTPS.

* **the database** is protected by user/passwords. There is an admin database
  which uses the :code:`MONGO_ADMIN_URL`. This URL is not exposed to
  users. The per-user databases are only exposed on a per-user basis.

* **communication to the database** using mongo TSL support

* **communication to the message broker** access protection to RabbitMQ,
  channel encryption (TLS) and message signing.

* **configuration of client workstations**. via userid and apikey
