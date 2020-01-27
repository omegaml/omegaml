from omegaml.documents import MDREGISTRY


class PromotionMixin(object):
    """
    Promote objects from one bucket to another
    """

    def promote(self, name, other):
        """
        Promote object to another bucket.

        This effectively copies the object. If the objects exists in the
        target it will be replaced.

        Args:
            name: The name of the object
            bucket: the bucket to promote to
            other:

        Returns:
            The Metadata of the new object
        """
        if self == other:
            raise ValueError('cannot promote to self')
        # see if the backend supports explicit promotion
        backend = self.get_backend(name)
        if hasattr(backend, 'promote'):
            return backend.promote(name, other)
        # do default promotion, i.e. copy
        meta = self.metadata(name)
        obj = self.get(name)
        other.drop(name, force=True)
        # TODO refactor to promote of python native data backend
        if meta.kind == MDREGISTRY.PYTHON_DATA:
            # in case of native python data we get back a list of
            # all previously inserted objects. do the same in other
            [other.put(o, name) for o in obj]
            other_meta = other.metadata(name)
        else:
            other_meta = other.put(obj, name)
        return other_meta
