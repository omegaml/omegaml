import re
from inspect import isclass

from omegaml.backends.virtualobj import VirtualObjectBackend


class VirtualHelperBackend(VirtualObjectBackend):
    KIND = 'virtualobj.helper'

    def __init__(self, handler, store, model_store=None, data_store=None, tracking=None, backend=None, **kwargs):
        super().__init__(model_store=model_store, data_store=data_store, tracking=tracking, **kwargs)
        self.handler = handler  # the handler fn (virtualobj)
        self.store = store  # the store where we're at
        self.backend = backend  # the original backend

    def get(self, name, **kwargs):
        meta = self.store.metadata(name)
        data = self.handler(method='get', obj=None, name=name, meta=meta, store=self.store, backend=self.backend,
                            **kwargs)
        return data or self.backend.get(name, **kwargs)

    def put(self, obj, name, **kwargs):
        meta = self.store.metadata(name)
        handled_meta = self.handler(method='put', obj=obj, name=name, meta=meta, store=self.store, backend=self.backend,
                                    **kwargs)
        meta = handled_meta or self.backend.put(obj, name, **kwargs)
        meta.kind_meta.setdefault('helper', self.handler._handler_name)
        meta.save()
        return meta

    def drop(self, name, force=False, **kwargs):
        meta = self.store.metadata(name)
        result = self.handler(method='put', obj=name, meta=meta, force=force, **kwargs)
        return self.backend.drop(name, force=force, **kwargs) if result is None else result

    def predict(self, modelname, Xname=None, Yname=None, **kwargs):
        meta = self.store.metadata(modelname)
        model = self.get(modelname, **kwargs)
        data = self.data_store.get(Xname)
        result = self.handler(method='predict', obj=model, name=modelname, meta=meta, store=self.store,
                              backend=self.backend, data=data, **kwargs)
        return result


class ObjectHelperMixin:
    """ virtual backend support

    Enables the use of any virtualobj as a dynamically loaded backend

    Usage:
        A helper is a virtualobj that handles .get(), .put(), .drop() for an object, overriding or extending
        the actual backend responsible for handling objects of that kind. Unlike actual backends, helpers
        can be created, stored and deployed at runtime.::

            @virtualobj
            def myhelper(*args, method=None, obj=None, meta=None, store=None, backend=None, **kwargs):
                if method == 'get':
                    obj = ...
                    return obj
                if method == 'put':
                    save(obj)
                    return store.make_metadata(...)

            # store this helper
            om.models.put(myhelper, 'helpers/myhelper')

            # store some model using this helper, e.g. to support a new serialization format
            obj = Model(...)
            om.models.put(obj, 'mymodel', helper='helpers/myhelper')

        We can specify helpers to be automatically used for certain object types by adding
        the ``supports='<kind>|<type>[,...]'`` keyword.::

            om.models.put(myhelper, 'helpers/myhelper', supports='sklearn.*')

        This ensures 'helpers/myhelpers' is selected automatically to handle objects whose type is part
        of the sklearn library.

            # the .put() call will be handled by helper/myhelper
            model = sklearn.linear_model.LinearRegression()
            om.models.put(model, 'mymodel')

    .. versionadded:: NEXT
        add dynamic backends implemented as virtualobjects
    """

    def put(self, obj, name, supports=None, **kwargs):
        """ store a virtualobj as a helper for other objects

        Args:
            obj (any): any object supported by backends
            name (str): the name of the object
            supports (str): a support specification of the format ``<kind>|<module.name>[,...]``
            **kwargs: passed on to backend handling type(obj)

        Returns:
            Metadata
        """
        meta = super().put(obj, name, **kwargs)
        if supports:
            meta_helpers = self.put({}, '.helpers')
            all_supports = meta_helpers.attributes.setdefault('supports', {})
            all_supports[name] = supports
            meta_helpers.save()
        return meta

    def get_backend(self, name, model_store=None, data_store=None, helper=None, **kwargs):
        meta = self.metadata(name)
        if meta:
            backend = super().get_backend(name, model_store=model_store, data_store=data_store, **kwargs)
            helper = None if helper is False else (
                    helper or meta.kind_meta.get('helper') or self._resolve_supports(meta=meta))
            if helper:
                return self._get_handler(helper, model_store, data_store, backend, **kwargs)
        return super().get_backend(name, model_store=model_store, data_store=data_store, **kwargs)

    def get_backend_byobj(self, obj, name=None, model_store=None, data_store=None, helper=None, **kwargs):
        meta = self.metadata(name) if name else None
        backend = super().get_backend_byobj(obj, name, model_store=model_store, data_store=data_store, **kwargs)
        kind = getattr(backend, 'KIND', '__nobackend__')
        helper = helper or (meta.kind_meta.get('helper') if meta is not None else None) or self._resolve_supports(
            obj=obj, meta=meta, kind=kind)
        if helper:
            return self._get_handler(helper, model_store, data_store, backend)
        return backend

    def _get_handler(self, helper, model_store, data_store, backend, **kwargs):
        handler = self.get(helper, raw=True)
        handler._handler_name = helper
        model_store = model_store or self
        data_store = data_store or self
        return VirtualHelperBackend(handler, self, model_store=model_store, data_store=data_store,
                                    backend=backend, **kwargs)

    def _resolve_supports(self, obj=None, meta=None, kind=None):
        helpers_meta = self.metadata('.helpers')
        if not helpers_meta:
            return
        supports = helpers_meta.attributes.get('supports', {})
        default_ref = 'obj' if obj is not None else 'kind'
        obj_kind = (meta.kind if meta else kind) or '__nobackend__'
        obj_fqn = fully_qualified_name(obj)
        for helper, spec in supports.items():
            for parts in spec.split(','):
                ref, tspec = parts.split(':', 1) if ':' in spec else (default_ref, parts)
                match_kind = ref == 'kind' and re.match(tspec, obj_kind)
                match_obj = ref == 'obj' and re.match(tspec, obj_fqn)
                if match_kind or match_obj:
                    return helper


def fully_qualified_name(obj):
    """
    Return the fully‑qualified name of *obj* as a string.

    Works for functions, classes, methods, and class/instance attributes.
    """
    # For bound methods, the underlying function holds the real name
    if hasattr(obj, "__func__"):  # e.g. instance.method
        obj = obj.__func__
    if hasattr(obj, "__class__"):
        obj = obj.__class__

    module = getattr(obj, "__module__", None)
    qualname = getattr(obj, "__qualname__", None)

    if module and qualname:
        return f"{module}.{qualname}"
    elif module:
        return f'{module}'
    elif qualname:  # built‑ins like <class 'int'>
        return qualname
    elif isclass(obj):
        return repr(obj)
    return '__noname__'
