om.runtime
==========

.. contents::

.. autodata:: omegaml.runtime

    Methods to run models, scripts, jobs, experiments:

        - :py:meth:`omegaml.runtimes.OmegaRuntime.model`
        - :py:meth:`omegaml.runtimes.OmegaRuntime.script`
        - :py:meth:`omegaml.runtimes.OmegaRuntime.job`
        - :py:meth:`omegaml.runtimes.OmegaRuntime.experiment`

    Methods to manage task distribution, logging:

        - :py:meth:`omegaml.runtimes.OmegaRuntime.mode`
        - :py:meth:`omegaml.runtimes.OmegaRuntime.require`

    Methods to inspect runtime state:

        - :py:meth:`omegaml.runtimes.OmegaRuntime.ping`
        - :py:meth:`omegaml.runtimes.OmegaRuntime.queues`
        - :py:meth:`omegaml.runtimes.OmegaRuntime.workers`
        - :py:meth:`omegaml.runtimes.OmegaRuntime.stats`

    Backends:

        - :py:class:`omegaml.runtimes.modelproxy.OmegaModelProxy`
        - :py:class:`omegaml.runtimes.jobproxy.OmegaJobProxy`
        - :py:class:`omegaml.runtimes.scriptproxy.OmegaScriptProxy`
        - :py:class:`omegaml.runtimes.trackingproxy.OmegaTrackingProxy`
        - :py:class:`omegaml.runtimes.loky.OmegaRuntimeBackend`

    Mixins:

        - :py:class:`omegaml.runtimes.mixins.ModelMixin`
        - :py:class:`omegaml.runtimes.mixins.GridSearchMixin`
        - :py:class:`omegaml.runtimes.mixins.taskcanvas.CanvasTask`

.. autoclass:: omegaml.runtimes.OmegaRuntime
   :members:

Backends
--------

.. autoclass:: omegaml.runtimes.modelproxy.OmegaModelProxy
   :members:

.. autoclass:: omegaml.runtimes.jobproxy.OmegaJobProxy
   :members:

.. autoclass:: omegaml.runtimes.scriptproxy.OmegaScriptProxy
   :members:

.. autoclass:: omegaml.runtimes.loky.OmegaRuntimeBackend
   :members:

.. autoclass:: omegaml.runtimes.trackingproxy.OmegaTrackingProxy
   :members:

Mixins
------

.. autoclass:: omegaml.runtimes.mixins.ModelMixin
   :members:

.. autoclass:: omegaml.runtimes.mixins.GridSearchMixin
   :members:

.. autoclass:: omegaml.runtimes.mixins.taskcanvas.CanvasTask
   :members:


