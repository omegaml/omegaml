class CombinedOmegaStoreMixin:
    def __init__(self, stores):
        self._stores = stores

    def get(self, name, *args, **kwargs):
        store, store_name = self._get_store(name)
        return store.get(store_name, *args, **kwargs)

    def put(self, obj, name, *args, **kwargs):
        store, store_name = self._get_store(name)
        return store.put(obj, store_name, *args, **kwargs)

    def list(self, pattern=None, regexp=None, **kwargs):
        index = []
        pattern = pattern or ''
        for store in self._stores:
            index.extend(f'{store.prefix}{name}' for name in store.list(pattern.replace(store.prefix, ''),
                                                                        regexp=(regexp.replace(
                                                                            store.prefix) if regexp else regexp),
                                                                        **kwargs))
        return index

    def help(self, name_or_obj):
        import sys
        import pydoc

        if isinstance(name_or_obj, str):
            try:
                store, store_name = self._get_store(name_or_obj)
            except ValueError as e:
                pass
            else:
                return store.help(store_name)
        return help(name_or_obj) if sys.flags.interactive else pydoc.render_doc(name_or_obj, renderer=pydoc.plaintext)

    def metadata(self, name):
        store, store_name = self._get_store(name)
        return store.metadata(store_name)

    def _get_store(self, name):
        for store in self._stores:
            if name.startswith(store.prefix):
                return store, name.replace(store.prefix, '')
        prefixes = [s.prefix for s in self._stores]
        raise ValueError(f'there is no store for {name}, try prefixing with any of {prefixes}')
