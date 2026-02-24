om.scripts
==========

.. contents::

.. autodata:: omegaml.scripts

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

        - :py:class:`omegaml.mixins.store.package.PythonPackageMixin`

    Backends:

        - :py:class:`omegaml.backends.package.PythonPackageData`
        - :py:class:`omegaml.backends.package.PythonPipSourcedPackageData`

        Backends for ``dash`` (loaded if installed)

        - :py:class:`omegaml.backends.dashapp.DashAppBackend`

        Backends for ``mlflow`` (loaded if installed)

        - :py:class:`omegaml.backends.mlflow.localprojects.MLFlowProjectBackend`
        - :py:class:`omegaml.backends.mlflow.gitprojects.MLFlowGitProjectBackend`

        Backends for ``R`` (loaded if installed)

        - :py:class:`omegaml.backends.rsystem.rscripts.RPackageData`


Backends
--------

.. autoclass:: omegaml.backends.package.PythonPackageData
    :members:

    .. autoattribute:: KIND


.. autoclass:: omegaml.backends.package.PythonPipSourcedPackageData
    :members:

    .. autoattribute:: KIND


.. autoclass:: omegaml.backends.dashapp.DashAppBackend
    :members:

    .. autoattribute:: KIND


.. autoclass:: omegaml.backends.mlflow.localprojects.MLFlowProjectBackend
    :members:

    .. autoattribute:: KIND


.. autoclass:: omegaml.backends.mlflow.gitprojects.MLFlowGitProjectBackend
    :members:

    .. autoattribute:: KIND


.. autoclass:: omegaml.backends.rsystem.rscripts.RPackageData
    :members:

    .. autoattribute:: KIND

Mixins
------

.. autoclass:: omegaml.mixins.store.package.PythonPackageMixin
    :members:

Helpers
-------

.. autoclass:: omegaml.backends.rsystem.rscripts.RScript
    :members:

