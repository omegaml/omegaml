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
        if self.bucket == other.bucket and self.prefix == other.prefix:
            raise ValueError('cannot promote to self')
        # see if the backend supports explicit promotion
        backend = self.get_backend(name)
        if hasattr(backend, 'promote'):
            return backend.promote(name, other)
        # do default promotion
        obj = self.get(name)
        other.drop(name, force=True)
        return other.put(obj, name)
