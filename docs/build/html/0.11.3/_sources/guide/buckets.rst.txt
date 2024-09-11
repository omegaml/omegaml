Multiple environments
=====================

omega|ml provides three concepts to work with multiple environments, each focussed on a specific need.

* :code:`context` - a context provides a completely seperate environment, where all datasets, models,
  jobs as well as the runtime is distinct from any other other context. Think of this is the equivalent
  of a seperate account.

* :code:`buckets` - a bucket is a logical subset of a context. It utilizes the same database and the
  same runtime as any other bucket within the same context. Think of this a a top-level folder in
  an other-wise shared environment.

* :code:`runtime routing` - tasks submitted to the runtime can specify resource requirements, which
  effectively route tasks to different workers. Multiple contexts can use the same runtime resources.
  Think of this as compute cluster segregation e.g. by client or project.

Working with Contexts
---------------------

omega|ml contexts are created by calling the :code:`om.setup()` function, returning a configured
:code:`Omega()` instance:

.. code::

    # development environment
    om_dev = om.setup(mongo_url=...., celeryconf=....)
    # production environment
    om_prod = om.setup(mongo_url=...., celeryconf=....)


Working with Buckets
--------------------

Each :code:`Omega` instance is configured to a particular bucket, the default being :code:`omega`. To
get an instantance configured for an other bucket use:

.. code:: python

    om_foo = om['mybucket']

Buckets are an easy built-in way to separate environments, projects and users. For example,

.. code:: python

    # an environment for user1
    om_user1 = om['user1']
    # an environment for project_a
    om_prjA = om['projec_a']
    # development
    om_dev = om['dev']
    # production
    om_prod = om['prod']
    # etc.


Promoting objects between contexts and environments
---------------------------------------------------

Object promotion copies objects from one context to another, more specifically from one bucket to another bucket.


.. note::

    Promoition is more than a simple copy: Some objects may require conditions to be met
    (e.g. a model must be trained) before the promotion works. The default implementation
    of object promotion does not impose any conditions and works as a copy/replace.


.. code:: python

    om_dev.datasets.promote('sales', om_prod.datasets)
    om_dev.models.promote('sales-prediction', om_prod.models)
