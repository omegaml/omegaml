import re


from omegaml.backends.virtualobj import VirtualObjectBackend


class VirtualObjectMixin(object):
    """
    process virtual objects

    This checks if an object is a VirtualObject and if so
    retrieves the handler and processes it.
    """

    def __init__(self):
        self.__meta = None

    def _isvirtual(self, name):
        self.__meta = self.metadata(name)
        return (self.__meta is not None and
                self.__meta.kind == VirtualObjectBackend.KIND)

    def _getvirtualobjfn(self, name):
        virtualobjfn = super(VirtualObjectMixin, self).get(name)
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
        raw = kwargs.get('raw', False)
        should_version = self._model_version_applies(name)
        raw = raw or should_version
        name, kwargs = self._resolve_realname(name, kwargs)
        if not raw and self._isvirtual(name):
            handler = self._getvirtualobjfn(name)
            result = handler(method='get', meta=self.__meta, store=self, **kwargs)
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
                                                 meta=self.__meta, store=self, **kwargs)
        else:
            result = super(VirtualObjectMixin, self).put(obj, name, attributes=attributes, **kwargs)
        return result

    def drop(self, name, force=False, **kwargs):
        version = kwargs.get('version')
        should_version = version is not None or self._model_version_applies(name)
        if not should_version and self._isvirtual(name):
            try:
                handler = self._getvirtualobjfn(name)
                result = handler(method='drop', meta=self.__meta, store=self, force=force)
            except:
                if not force:
                    raise
            else:
                if result is False:
                    return False
        return super(VirtualObjectMixin, self).drop(name, force=force, **kwargs)

