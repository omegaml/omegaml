class CombinedOmegaStoreMixin:
    def __init__(self, stores):
        self._stores = stores

    def get(self, name, *args, **kwargs):
        store, store_name = self.store_by_name(name)
        return store.get(store_name, *args, **kwargs)

    def put(self, obj, name, *args, **kwargs):
        store, store_name = self.store_by_name(name)
        return store.put(obj, store_name, *args, **kwargs)

    def list(self, pattern=None, regexp=None, raw=False, **kwargs):
        index = []
        pattern = pattern or ''
        for store in self._stores:
            regexp = regexp.replace(store.prefix) if regexp else None
            # list by name|pattern, return list of Metadata or list of names
            members = store.list(pattern.replace(store.prefix, '', 1),
                                 regexp=regexp, raw=raw, **kwargs)
            # either add obj:Metadata as is, or obj:str as 'prefix/name'
            add = lambda obj: f'{store.prefix}{obj}' if not raw else obj
            index.extend(add(obj) for obj in members)
        return index

    def help(self, name_or_obj):
        import sys
        import pydoc

        if isinstance(name_or_obj, str):
            try:
                store, store_name = self.store_by_name(name_or_obj)
            except ValueError as e:
                pass
            else:
                return store.help(store_name)
        return help(name_or_obj) if sys.flags.interactive else pydoc.render_doc(name_or_obj, renderer=pydoc.plaintext)

    def metadata(self, name, **kwargs):
        store, store_name = self.store_by_name(name)
        return store.metadata(store_name, **kwargs)

    def stores_prefixes(self):
        return [s.prefix for s in self._stores]

    def store_by_prefix(self, prefix):
        prefix = prefix.replace('datasets/', 'data/')
        for store in self._stores:
            if store.prefix == prefix:
                return store
        raise ValueError(f'there is no store for {prefix}')

    def store_by_meta(self, meta):
        return self.store_by_prefix(meta.prefix)

    def store_by_name(self, name):
        for store in self._stores:
            if name.startswith(store.prefix):
                return store, name.replace(store.prefix, '')
        prefixes = [s.prefix for s in self._stores]
        raise ValueError(f'there is no store for {name}, try prefixing with any of {prefixes}')
