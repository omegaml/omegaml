from omegaml.documents import MDREGISTRY


class PromotionMixin(object):
    """
    Promote objects from one bucket to another
    """
    DEFAULT_DROP = {
        'models/': False, # models are versioned, don't drop
    }

    @classmethod
    def supports(cls, store, **kwargs):
        return store.prefix in ('data/', 'jobs/', 'models/', 'scripts/', 'streams/')

    def promote(self, name, other, asname=None, drop=None, **kwargs):
        """
        Promote object to another bucket.

        This effectively copies the object. If the objects exists in the
        target it will be replaced.

        Args:
            name: The name of the object
            other: the OmegaStore instance to promote to
            asname: the name to use in other, defaults to .metadata(name).name
            kwargs: will be forwarded to other.put

        Returns:
            The Metadata of the new object
        """
        drop = drop if drop is not None else self.DEFAULT_DROP.get(self.prefix, True)
        # sanity checks
        # -- promotion by same name requires a different store
        meta = self.metadata(name)
        asname = asname or meta.name
        if name == asname and self == other:
            raise ValueError(f'must specify asname= different from {meta.name}')
        # see if the backend supports explicit promotion
        backend = self.get_backend(name)
        if hasattr(backend, 'promote'):
            return backend.promote(name, other, asname=asname, **kwargs)
        # do default promotion, i.e. copy
        meta = self.metadata(name)
        obj = self.get(name)
        asname = asname or meta.name
        other.drop(asname, force=True) if drop else None
        # TODO refactor to promote of python native data backend
        if meta.kind == MDREGISTRY.PYTHON_DATA:
            # in case of native python data we get back a list of
            # all previously inserted objects. do the same in other
            [other.put(o, asname) for o in obj]
            other_meta = other.metadata(asname)
        else:
            other_meta = other.put(obj, asname, **kwargs)
        return other_meta
