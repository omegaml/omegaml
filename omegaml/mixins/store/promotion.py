from pathlib import Path

from functools import partial

from omegaml.documents import MDREGISTRY
from omegaml.util import dict_merge


class PromotionMixin(object):
    """ Promote objects from one bucket to another

    Promotion Methods:
        * `getput` - performs target.put(source.get()) and copies metadata
           attributes by merging target.metadata's .attributes and .kind_meta
        * `metadata` - creates a new metadata data entry in target, copying
            metadata attributes and kind_meta. Does not get/put the object itself
            (i.e. no associated data is promoted).
        * `data` - like `getput`, but does not merge metadata
        * `export` - performs .to_archive() and .from_archive(), effectively
             copying metadata, the associated gridfile (if available) and collection
             data (if available). This is equivalent to `om runtime export`.

        The default promotion method is getput(), or the object's backend.PROMOTE
        method, if specified.

    Some object backends provide a default promotion other than getput:

    * sqlalchemy.conx - uses the `metadata` promotion, effectively copying only
       metadata. Use promote(..., method='metadata,data') to also promote data

    * virtualobj.dill - uses the `export` promotion, effectively copying all
       metadata and the associated @virtualobj function. If the source object
       is a versioned model, this copies the current version and metadata. To
       copy a specific version, use promote('model@version'). To create a
       new version in the target bucket use promote(..., method='getput').
    """
    DEFAULT_DROP = {
        'models/': False,  # models are versioned, don't drop
    }

    @classmethod
    def supports(cls, store, **kwargs):
        return store.prefix in ('data/', 'jobs/', 'models/', 'scripts/', 'streams/')

    def promote(self, name, other, asname=None, drop=None, method='default', get=None,
                put=None, **kwargs):
        """ Promote object to another store.

        This effectively copies the object. If the objects exists in the
        target it will be replaced.

        Args:
            name: The name of the object
            other: the OmegaStore instance to promote to
            asname: the name to use in other, defaults to .metadata(name).name
            drop (bool): if True calls other.drop(force=True) before promoting, defaults to False
            method (str|list): specify the method or multiple methods in sequence, available methods
               are 'default', 'getput', 'metadata', 'data'. For 'default', the object backend's
               .PROMOTE property is used, defaulting to 'getput'
            get (dict): optional, specifies the store.get(**kwargs)
            put (dict): optional, specifies the other.put(**kwargs)
            kwargs: additional kwargs are passed to the initial other.put(), for metadata promotion

        Returns:
            The Metadata of the new object
        """
        from omegaml.store import OmegaStore
        assert isinstance(other, OmegaStore), f"specify promote(..., other, ...) as om.models, not {type(other)}"
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
            return backend.promote(name, other, asname=asname, drop=drop, get=get, put=put,
                                   method=method, **kwargs)
        # run all promotion methods as requested or provided by the backend
        methods = method.split(',') if isinstance(method, str) else method
        promotion_methods = self.promotion_methods(name, other, asname=asname, drop=drop,
                                                   get=get, put=put, backend=backend, **kwargs)
        [promotion_methods[m]() for m in methods]
        return other.metadata(asname)

    def promotion_methods(self, name, other, asname=None, drop=None,
                          get=None, put=None, backend=None, **kwargs):
        # do default promotion, i.e. get()/put()
        PROMOTION_METHODS = {
            'getput': partial(self._get_put_promotion, name, other, asname=asname, drop=drop),
            'data': partial(self._data_promotion, name, other, asname=asname, get=get, put=put,
                            **kwargs),
            'metadata': partial(self._metadata_promotion, name, other, asname=None, drop=False,
                                get=get, put=put, **kwargs),
            'export': partial(self._export_promotion, name, other, asname=None, drop=False,
                              get=get, put=put, **kwargs),
        }
        default_method = PROMOTION_METHODS[getattr(backend, 'PROMOTE', 'getput')]
        PROMOTION_METHODS['default'] = lambda *args, **kwargs: default_method(*args, **kwargs)
        return PROMOTION_METHODS

    def _get_put_promotion(self, name, other, asname=None, drop=None, get=None, put=None, **kwargs):
        get_kwargs = get or kwargs
        put_kwargs = put or kwargs
        meta = self.metadata(name)
        obj = self.get(name, **get_kwargs)
        asname = asname or meta.name
        other.drop(asname, force=True) if drop else None
        # TODO refactor to promote of python native data backend
        if meta.kind == MDREGISTRY.PYTHON_DATA:
            # in case of native python data we get back a list of
            # all previously inserted objects. do the same in other
            [other.put(o, asname) for o in obj]
            other_meta = other.metadata(asname)
        else:
            other_meta = other.put(obj, asname, **put_kwargs)
        # promote metadata, exception versions
        # TODO: move versions to kind_meta, which is not promoted
        meta.attributes.pop('versions', None)
        dict_merge(other_meta.attributes, meta.attributes)
        other_meta.save()
        return other_meta

    def _metadata_promotion(self, name, other, asname=None, drop=False, **kwargs):
        """ promote metadata

        This is called by PromotionMixin.promote() to promote metadata
        to another store, not data.

        Args:
            name (str): the name of the object
            other (om.datasets): the other om.datasets

        Returns:
            Metadata of the promoted dataset as the result of other.put()
        """
        meta = self.get.metadata(name)
        asname = asname or meta.name
        other.drop(asname, force=True) if drop else None
        other_meta = other.make_metadata(asname, meta.kind, bucket=other.bucket,
                                         prefix=other.prefix, **kwargs)
        other_meta.kind_meta.update(meta.kind_meta)
        other_meta.attributes.update(meta.attributes)
        other_meta.save()
        return other_meta

    def _data_promotion(self, name, other, asname=None, get=None, put=None, **kwargs):
        """ promote data

        This is called by PromotionMixin.promote() to promote an object's data
        to another store. If source.get() returns an interator, target.put() will
        be called for every iteration.
        """
        asname = asname or name
        get_kwargs = get or kwargs
        put_kwargs = put or kwargs
        to_copy = self.get(name, **get_kwargs)
        if hasattr(to_copy, '__iter__'):
            for chunk in to_copy:
                other.put(chunk, asname, **put_kwargs)
        else:
            other.put(to_copy, asname, **put_kwargs)
        other_meta = other.metadata(asname)
        return other_meta.save()

    def _export_promotion(self, name, other, asname=None, get=None, put=None, **kwargs):
        """ promote as export/import

        This is called by PromotionMixin.promote() to promote an object's data
        to another store in the way that the `om runtime export/import` commands do.
        This includes exporting all data and metadata associated with an object.
        """
        asname = asname or name
        get_kwargs = get or kwargs
        put_kwargs = put or kwargs
        arc = self.to_archive(name, Path(self.tmppath) / asname, **get_kwargs)
        other_meta = other.from_archive(arc, asname, **put_kwargs)
        return other_meta
