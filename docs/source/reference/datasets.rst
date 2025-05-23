om.datasets
===========

.. contents::

.. autodata:: omegaml.datasets

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

        - :py:class:`omegaml.mixins.store.ProjectedMixin`
        - :py:class:`omegaml.mixins.store.LazyGetMixin`
        - :py:class:`omegaml.mixins.store.virtualobj.VirtualObjectMixin`
        - :py:class:`omegaml.mixins.store.promotion.PromotionMixin`
        - :py:class:`omegaml.mixins.mdf.iotools.IOToolsStoreMixin`
        - :py:class:`omegaml.mixins.store.extdmeta.ExtendedMetadataMixin`

    Backends:

        - :py:class:`omegaml.backends.npndarray.NumpyNDArrayBackend`
        - :py:class:`omegaml.backends.virtualobj.VirtualObjectBackend`
        - :py:class:`omegaml.backends.rawdict.PandasRawDictBackend`
        - :py:class:`omegaml.backends.rawfiles.PythonRawFileBackend`

        Backends for ``openai`` (loaded if installed)

        .. versionadded:: 0.17.0

        - :py:class:`omegaml.backends.genai.mongovector.MongoDBVectorStore`
        - :py:class:`omegaml.backends.genai.pgvector.PGVectorBackend`



Backends
--------

.. autoclass:: omegaml.backends.sqlalchemy.SQLAlchemyBackend
    :members:

    .. autoattribute:: KIND

.. autoclass:: omegaml.backends.npndarray.NumpyNDArrayBackend
    :members:

    .. autoattribute:: KIND

.. autoclass:: omegaml.backends.virtualobj.VirtualObjectBackend
    :members:

    .. autoattribute:: KIND

.. autoclass:: omegaml.backends.rawdict.PandasRawDictBackend
    :members:

    .. autoattribute:: KIND

.. autoclass:: omegaml.backends.rawfiles.PythonRawFileBackend
    :members:

    .. autoattribute:: KIND

.. autoclass:: omegaml.backends.genai.mongovector.MongoDBVectorStore
    :members:

    .. autoattribute:: KIND

.. autoclass:: omegaml.backends.genai.pgvector.PGVectorBackend

Mixins
------

.. autoclass:: omegaml.mixins.store.ProjectedMixin
   :members:

.. autoclass:: omegaml.mixins.store.LazyGetMixin
   :members:

.. autoclass:: omegaml.mixins.store.virtualobj.VirtualObjectMixin
   :members:

.. autoclass:: omegaml.mixins.store.promotion.PromotionMixin
   :members:

.. autoclass:: omegaml.mixins.mdf.iotools.IOToolsStoreMixin
   :members:

.. autoclass:: omegaml.mixins.store.extdmeta.ExtendedMetadataMixin
   :members:

