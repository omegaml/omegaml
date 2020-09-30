class CombinedOmegaStoreMixin:
    def __init__(self, stores):
        self._stores = stores

    def get(self, name, *args, **kwargs):
        store = self._get_store(name)
        return store.get(name.replace(store.prefix, ''), *args, **kwargs)

    def put(self, obj, name, *args, **kwargs):
        store = self._get_store(name)
        return store.put(obj, name.replace(store.prefix, ''), *args, **kwargs)

    def list(self, pattern=None, regexp=None, **kwargs):
        index = []
        pattern = pattern or ''
        for store in self._stores:
            index.extend(f'{store.prefix}{name}' for name in store.list(pattern.replace(store.prefix, ''),
                                                                        regexp=(regexp.replace(
                                                                            store.prefix) if regexp else regexp),
                                                                        **kwargs))
        return index

    def metadata(self, name):
        store = self._get_store(name)
        return store.metadata(name.replace(store.prefix, ''))

    def help(self, name_or_obj):
        store = self._get_store(name_or_obj)
        return store.help(name_or_obj)

    def _get_store(self, name):
        for store in self._stores:
            if name.startswith(store.prefix):
                return store
        prefixes = [s.prefix for s in self._stores]
        raise ValueError(f'there is no store for {name}, try prefixing with any of {prefixes}')
