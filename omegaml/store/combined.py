from collections import defaultdict


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
            pattern = pattern.replace(store.prefix, '', 1)
            # list by name|pattern, return list of Metadata or list of names
            members = store.list(pattern=pattern,
                                 regexp=regexp, raw=raw, **kwargs)
            # either add obj:Metadata as is, or obj:str as 'prefix/name'
            add = lambda obj: f'{store.prefix}{obj}' if not raw else obj
            index.extend(add(obj) for obj in members)
        return index

    def stats(self, pattern=None, regexp=None, summary=True, raw=False, scale=1.0,
              as_dict=False, **kwargs):
        """ return summary statistics by store

        Args:
            pattern (str): patterns of members to select, see .list() for details
            regexp (str): regex of members to select, see .list() for details
            summary (bool): if True, return summary statistics, else return raw statistics, defaults to True
            raw (bool): if True, return detail statistics for each member, equivalent of calling .stats() on each member
            scale (float): scale size statistics by this factor, defaults to 1.0 (bytes), set to 1e3 for KB, 1e6 for MB,
              1e9 for GB, etc.
            as_dict (bool): if True, return statistics as dict, else as DataFrame, defaults to False
            **kwargs:

        Returns:

        """
        _stats = defaultdict(dict)
        raw = raw is True or not summary
        for store in self._stores:
            if not hasattr(store, 'stats'):
                continue
            prefix = store.prefix.replace('/', '').replace('data', 'datasets')
            member_stats = store.stats(pattern=pattern, regexp=regexp, scale=scale, as_dict=True)
            if raw:
                _stats[prefix] = member_stats
            else:
                # summarize by store
                # -- member_stats is a dict of {member: {stat: value, ...}, ...}
                for mk, ms in member_stats.items():
                    for k in ms:
                        _stats[prefix].update({
                            # we count the number of members, not their collection size (in rows)
                            k: _stats[prefix].get(k, 0) + (1 if k == 'count' else ms[k])
                        })
        return _stats if as_dict else self.store_by_prefix('data')._get_stats_dataframe(_stats, scale=scale)

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
        prefix = prefix + '/' if not prefix.endswith('/') else prefix
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
