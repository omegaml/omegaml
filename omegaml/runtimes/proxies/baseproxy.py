from omegaml.util import extend_instance


class RuntimeProxyBase:
    """ Base class for runtime proxies

    Runtime proxies are used to provide a runtime context for a specific type
    of object, such as a model, script or job. This base class provides
    common functionality for all runtime proxies, in particular the ability
    to apply mixins and runtime.require() kwargs specified in the object's
    metadata.
    """

    def __init__(self, name, runtime=None, store=None):
        self.name = name
        self.runtime = runtime
        self.store = store
        self._apply_mixins()
        self._apply_require()

    def __repr__(self):
        return f'{self.__class__.__name__}({self.name})'

    def _apply_mixins(self):
        """
        apply mixins in defaults.OMEGA_RUNTIME_MIXINS
        """
        for mixin in self._mixins:
            extend_instance(self, mixin)

    @property
    def _mixins(self):
        return self.runtime.omega.defaults.OMEGA_RUNTIME_MIXINS

    def _apply_require(self):
        self.meta = meta = self.store.metadata(self.name)
        assert meta is not None, f"{self.store.prefix}{self.name} does not exist".format(**locals())
        # get common require kwargs
        require_kwargs = meta.attributes.get('require', {})
        tracking_specs = meta.attributes.get('tracking', {})
        # enable tracking by current runtime label, unless explicitly tracked
        label = self.runtime._common_kwargs['routing'].get('label')
        label = label or require_kwargs.get('label') or 'default'
        should_track = label in tracking_specs
        already_tracked = self.runtime._common_kwargs['task'].get('__experiment')
        if not already_tracked and should_track:
            require_kwargs.update({
                'task': dict(__experiment=meta.attributes['tracking'].get(label))
            })
        self.runtime.require(**require_kwargs, override=False) if require_kwargs else None

    def require(self, label=None, always=False, drop=False, **kwargs):
        """
        set require kwargs in metadata for this object, or override the
        runtime.require() kwargs for this object only

        Args:
            label: the label to use, if any
            drop: if True, drop all require kwargs from metadata
            always: if True, set the require kwargs in the object's metadata,
                else only set them on the runtime. Defaults to False
            **kwargs: the require kwargs. The kwargs are the same as for
                runtime.require(), except that they are stored in the
                object's metadata. Upon every task submitted to the runtime
                these kwargs will be set as om.runtime.require(**kwargs)

        Returns:
            if always is True, the metadata object, else self

        Notes:
            * if always is True (the default), the require kwargs are stored
              in the object's metadata. This means that upon every task
              submitted to the runtime these kwargs will be set as
              om.runtime.require(**kwargs), irrespective of the runtime's require kwargs
            * if always is False, the require kwargs are only set on runtime and override
              the runtime's require kwargs
        """
        if label:
            kwargs.update(label=label)
        if always:
            meta = self.store.metadata(self.name)
            meta.attributes['require'] = kwargs if not drop else {}
            result = meta.save()
        else:
            self.runtime.require(**kwargs)
            result = self
        return result
