import re

from omegaml.backends.virtualobj import VirtualObjectBackend


class VirtualObjectMixin(object):
    """
    process virtual objects

    This checks if an object is a VirtualObject and if so
    retrieves the handler and processes it.
    """

    def __init__(self):
        self._vobj_meta = None

    def _isvirtual(self, name):
        self._vobj_meta = self.metadata(name)
        return (self._vobj_meta is not None and
                self._vobj_meta.kind == VirtualObjectBackend.KIND)

    def _getvirtualobjfn(self, name, **kwargs):
        virtualobjfn = super(VirtualObjectMixin, self).get(name, **kwargs)
        if isinstance(virtualobjfn, type):
            virtualobjfn = virtualobjfn()
        return virtualobjfn

    def _resolve_realname(self, name, kwargs):
        # parse names in the format name{a=b,c=d} to name and update kwargs
        if isinstance(name, str) and all(c in name for c in '{}'):
            rx = r"(\w*=\w*)*"
            real_name, fn_kwargs = name.split('{', 1)
            fn_kwargs = fn_kwargs.split('}')[0]
            matches = (v.split('=') for v in re.findall(rx, fn_kwargs) if v)
            fn_kwargs = {
                k: v for k, v in matches
            }
            kwargs.update(fn_kwargs)
            name = real_name
        return name, kwargs

    def metadata(self, name, **kwargs):
        dsname, _ = self._resolve_realname(name, kwargs)
        return super().metadata(dsname)

    def get(self, name, **kwargs):
        # pass along some options to other mixins
        raw = kwargs.get('raw')
        should_version = self._model_version_applies(name)
        raw = raw if raw is not None else should_version
        name, kwargs = self._resolve_realname(name, kwargs)
        if not raw and self._isvirtual(name):
            handler = self._getvirtualobjfn(name)
            result = handler(method='get', meta=self._vobj_meta, store=self, **kwargs)
        else:
            result = super(VirtualObjectMixin, self).get(name, **kwargs)
        return result

    def put(self, obj, name, replace=False, attributes=None, **kwargs):
        # pass along some options to other mixins
        raw = kwargs.get('raw', False)
        noversion = kwargs.get('noversion')
        name, kwargs = self._resolve_realname(name, kwargs)
        should_version = bool(noversion) if noversion is not None else self._model_version_applies(name)
        raw = raw if raw is not None else should_version
        if not should_version and not raw and not replace and self._isvirtual(name):
            result = self._getvirtualobjfn(name)(data=obj, method='put',
                                                 meta=self._vobj_meta, store=self, **kwargs)
        else:
            result = super(VirtualObjectMixin, self).put(obj, name, attributes=attributes, replace=replace, **kwargs)
        return result

    def drop(self, name, force=False, **kwargs):
        version = kwargs.get('version')
        should_version = version is not None or self._model_version_applies(name)
        if not should_version and self._isvirtual(name):
            try:
                handler = self._getvirtualobjfn(name)
                result = handler(method='drop', meta=self._vobj_meta, store=self, force=force)
            except Exception as e:
                if not force:
                    raise
            else:
                if not force:
                    return bool(result)
        return super(VirtualObjectMixin, self).drop(name, force=force, **kwargs)
