om.models
=========

.. contents::

.. autodata:: omegaml.models

    Methods:

        - :py:meth:`omegaml.store.base.OmegaStore.list`
        - :py:meth:`omegaml.store.base.OmegaStore.get`
        - :py:meth:`omegaml.store.base.OmegaStore.getl`
        - :py:meth:`omegaml.store.base.OmegaStore.put`
        - :py:meth:`omegaml.store.base.OmegaStore.drop`
        - :py:meth:`omegaml.store.base.OmegaStore.exists`
        - :py:meth:`omegaml.store.base.OmegaStore.metadata`
        - :py:meth:`omegaml.store.base.OmegaStore.help`

    Mixins:

        - :py:class:`omegaml.mixins.store.virtualobj.VirtualObjectMixin`
        - :py:class:`omegaml.mixins.store.promotion.PromotionMixin`

    Backends:

        - :py:class:`omegaml.backends.experiment.ExperimentBackend`
        - :py:class:`omegaml.backends.scikitlearn.ScikitLearnBackend`

        Backends for ``tensorflow`` (loaded only if installed):

        - :py:class:`omegaml.backends.tensorflow.TensorflowKerasBackend`
        - :py:class:`omegaml.backends.tensorflow.TensorflowKerasSavedModelBackend`
        - :py:class:`omegaml.backends.tensorflow.TensorflowSavedModelBackend`
        - :py:class:`omegaml.backends.tensorflow.TFEstimatorModelBackend`

        Backends for ``keras`` (loaded only if installed):

        - :py:class:`omegaml.backends.keras.KerasBackend`

        Backends for ``mlflow`` (loaded only if installed)

        - :py:class:`omegaml.backends.mlflow.models.MLFlowModelBackend`
        - :py:class:`omegaml.backends.mlflow.registrymodels.MLFlowRegistryBackend`

        Backends for ``R`` (loaded if installed)

        - :py:class:`omegaml.backends.rsystem.rmodels.RModelBackend`

Backends
--------

.. autoclass:: omegaml.backends.scikitlearn.ScikitLearnBackend
    :members:

    .. autoattribute:: KIND

.. autoclass:: omegaml.backends.experiment.ExperimentBackend
    :members:

    .. autoattribute:: KIND

.. autoclass:: omegaml.backends.tensorflow.TensorflowKerasBackend
    :members:

    .. autoattribute:: KIND

.. autoclass:: omegaml.backends.tensorflow.TensorflowKerasSavedModelBackend
    :members:

    .. autoattribute:: KIND

.. autoclass:: omegaml.backends.tensorflow.TensorflowSavedModelBackend
    :members:

    .. autoattribute:: KIND

.. autoclass:: omegaml.backends.tensorflow.TFEstimatorModelBackend
    :members:

    .. autoattribute:: KIND

.. autoclass:: omegaml.backends.rsystem.rmodels.RModelBackend
    :members:

    .. autoattribute:: KIND


Mixins
------

.. autoclass:: omegaml.mixins.store.virtualobj.VirtualObjectMixin
   :members:

.. autoclass:: omegaml.mixins.store.promotion.PromotionMixin
   :members:

Helpers
-------

.. autoclass:: omegaml.backends.rsystem.rmodels.RModelProxy
    :members:
