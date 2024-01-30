from datetime import datetime
import cachetools

from omegaml.util import ProcessLocal

#: the object cache as name => (obj, last_update)
OBJECT_CACHE = ProcessLocal(cache=cachetools.TTLCache(maxsize=1000, ttl=60))


# FIXME fails (corrupts cache) for different buckets and different Omega instances
#       solve: cached name must include database and bucket name
#       in case of different omega users, the cache should be cleared on user change? [group users?]

class CachedObjectMixin:
    def _should_cache(self, name, **kwargs):
        byname = name.startswith('cached/')
        bymeta = False
        if not byname:
            meta = self.metadata(name, **kwargs)
            bymeta = meta.attributes.get('cached', False)
        return (byname or bymeta)

    def _should_refresh(self, name, **kwargs):
        cached, last_update = self._object_cache.get(name, (None, None))
        if last_update:
            meta = self.metadata(name, **kwargs)
            return meta.modified > last_update
        return False

    @property
    def _object_cache(self):
        return OBJECT_CACHE

    def _remove_from_cache(self, name=None):
        if name:
            self._object_cache.pop(name, None)
        else:
            self._object_cache.clear()

    def get(self, name, force=False, **kwargs):
        if self._should_cache(name, **kwargs):
            if force or self._should_refresh(name):
                del self._object_cache[name]
            cached, updated = self._object_cache.get(name) or (None, None)
            obj = cached or super().get(name, **kwargs)
            self._object_cache[name] = obj, datetime.now()
        else:
            self._object_cache.pop(name, None)
            obj = super().get(name, **kwargs)
        return obj

    def put(self, obj, name, **kwargs):
        meta = super().put(obj, name, **kwargs)
        self._object_cache[name] = obj, datetime.now()
        return meta
