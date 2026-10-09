omegaml.runtime.experiment
==========================

.. contents::

Concepts
--------

* ``ExperimentBackend`` provides the storage layer (backend to ``om.models``)
* ``TrackingProvider`` provides the metrics logging API
* ``TrackingProxy`` provides live metrics tracking in runtime tasks


Backends
--------

.. autoclass:: omegaml.backends.experiment.ExperimentBackend
    :members:

    .. autoattribute:: KIND

Metrics Logging
---------------

.. autoclass:: omegaml.backends.experiment.TrackingProvider
    :members:

.. autoclass:: omegaml.backends.experiment.OmegaSimpleTracker
    :members:

.. autoclass:: omegaml.backends.experiment.OmegaProfilingTracker
    :members:

.. autoclass:: omegaml.backends.experiment.NoTrackTracker
    :members:

*for tensorflow*

.. autoclass:: omegaml.backends.experiment.TensorflowCallback
    :members:


Runtime Integration
-------------------

.. autoclass:: omegaml.runtimes.trackingproxy.OmegaTrackingProxy
    :members:

