Runtime Clusters
================

By default omega|ml uses a Celery cluster for remote computation. However
the runtime is flexible to other clusters, provided the cluster supports
submitting arbitrary functions (in particular, omegaml's task functions).

Celery Runtime (default)
------------------------

The Celery runtime is the default implementation, provided as
:code:`om.runtime`. It provides the following interfaces:

* :code:`.model()` - to get a model proxy to a remote model, :code:`OmegaModelProxy`
* :code:`.job()` - to get a job proxy to a remote job, :code:`OmegaJobProxy` *Enterprise Edition*
* :code:`.script()` - to get a script proxy to a remote script (lambda module), :code:`OmegaScriptProxy` *Enterprise Edition*

The model proxy supports most methods of scikit-learn models, e.g.

* :code:`fit()`
* :code:`predict()`
* :code:`transform()`
* etc.

.. note::

   All omega|ml proxies support the same interface, although the specific
   backend implementation may not support all functionality or apply slightly
   different semantics

See the `Working with Machine learning models`_ for more details.

The job proxy supports two methods:

* :code:`run()` - to run a job immediately
* :code:`schedule()` - to schedule a job in the future


Dask runtime
------------

*Experimental*

The Dask (distributed) runtime supports executing omega|ml tasks and jobs on a
dask cluster, using the same semantics as the celery cluster.

To enable the Dask cluster,

.. code::

   # get your omega instance
   om = Omega(...)

   # create a dask runtime and set it as the omega runtime
   om.runtime = OmegaRuntimeDask('http://dask-scheduler-host:port',
                                 auth=om.runtime.auth)


Once this is done, om.runtime works as with the default runtime, except that
now all tasks previously executed on the celery cluster will now be executed
on the dask cluster.


PySpark runtime
---------------

*Experimental*

It is possible to run the omega|ml Celery or Dask runtimes on Spark clusters.
Please write to support@omegaml.io for details.
