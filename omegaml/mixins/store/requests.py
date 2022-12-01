import threading
from contextlib import contextmanager
from functools import partial

nop = lambda *args, **kwargs: None


class RequestCache:
    """ provides caching for metadata during requests

    While processing user requests, metadata are often queried several times for
    different attributes. To avoid repeatedly hitting the database, RequestCache
    keeps a cache of Metadata entries during requests. Note this does _not_ cache
    actual objects, i.e. store.get() operations remain uncached.

    Usage::

        with store.request():
            ...
            meta = store.metadata(...)  # adds meta to cache
            ...
            meta = store.metadata(...)  # retrieves from cache
        # cache is cleared at end of request

        you may also start and close requests explicitly::

            store.start_request()
            ...
            store.close_request()

        Upon store.put() inside a request, the resulting metadata is
        also cached.

        It is also possible to create a request context for all
        stores at the same time::

            with om.request(...):
                ...

        If you already have a request, e.g. from your web application,
        you can pass along the request object::

            with om.request(request):
                ...

        You can get back the currently active request by querying::

            store.current_request
            om.current_request

        To refresh the cache during a request:

            meta = store.metadata(name, cached=False) # will hit the db
    """

    def _init_mixin(self, *args, **kwargs):
        self._request = threading.local()

    @contextmanager
    def request(self, request=None):
        try:
            self.start_request(request=request)
            yield
        finally:
            self.close_request()

    def start_request(self, request=None):
        if not getattr(self.defaults, 'OMEGA_STORE_CACHE', False):
            return
        self._request.active = True
        self._request_cache.clear()
        self._request.request = request or self._request

    def close_request(self):
        if not getattr(self.defaults, 'OMEGA_STORE_CACHE', False):
            return
        self._request.active = False
        self._request_cache.clear()
        self._request.request = None

    @property
    def current_request(self):
        return getattr(self._request, 'request', None)

    @property
    def _request_cache(self):
        if getattr(self._request, 'cache', None) is None:
            self._request.cache = {}
        return self._request.cache

    def metadata(self, name=None, cached=True, **kwargs):
        _base_meta = partial(super().metadata, name=name, **kwargs)
        if self.current_request:
            try:
                # if cached is False, we query the original metadata, yet still cache
                meta = self._request_cache[name] if cached else _base_meta()
            except:
                meta = _base_meta()
            # we only cache valid metadata objects
            # -- if there is no metadata, there is nothing to cache
            # -- if cached is False, we still cache to benefit later requests
            if meta is not None:
                self._request_cache[name] = meta
        else:
            meta = _base_meta()
        return meta

    def make_metadata(self, name, kind, **kwargs):
        # metadata is made to be saved, be sure to clear cache
        meta = super().make_metadata(name, kind, **kwargs)
        if self.current_request:
            self._request_cache.pop(name, None)
        return meta

    def put(self, obj, name, **kwargs):
        meta = super().put(obj, name, **kwargs)
        if self.current_request:
            if isinstance(meta, self._Metadata):
                self._request_cache[name] = meta
        return meta

    def drop(self, name, *args, **kwargs):
        if self.current_request:
            self._request_cache.pop(name, None)
        return super().drop(name, *args, **kwargs)


class CombinedStoreRequestCache:
    @contextmanager
    def request(self, request=None):
        try:
            self.start_request(request=request)
            yield
        finally:
            self.close_request()

    def start_request(self, request=None):
        [getattr(s, 'start_request', nop)(request=request) for s in self._stores]

    def close_request(self):
        [getattr(s, 'close_request', nop)() for s in self._stores]

    @property
    def current_request(self):
        return [getattr(s, 'current_request', None) for s in self._stores][0]
