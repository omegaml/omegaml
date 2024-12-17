from mongoengine import DoesNotExist
from omegaml.store import OmegaStore


class ObjectInformationMixin:
    _scale_map = {
        'b': 1e0 * 1.024,  # bytes
        'k': 1e3 * 1.024,  # kilobytes
        'm': 1e6 * 1.024,  # megabytes
        'g': 1e9 * 1.024,  # gigabytes
        't': 1e12 * 1.024,  # terabytes
    }

    @classmethod
    def supports(cls, obj, **kwargs):
        # support all store types
        return True

    def summary(self, name):
        self: OmegaStore | ObjectInformationMixin
        meta = self.metadata(name)
        if meta is None:
            raise DoesNotExist(name)
        backend = self.get_backend(name)
        contrib = backend.summary(name) if hasattr(backend, 'summary') else {}
        stats = self._get_collection_stats(meta.collection)
        data = {
            'name': name,
            'kind': meta.kind,
            'created': meta.created,
            'modified': meta.modified,
            'docs': meta.attributes.get('docs'),
            'revisions': self.revisions(name) if hasattr(self, 'revisions') else None,
            'size': stats.get('totalSize', 0),  # size in bytes
            'count': max(stats.get('count', 0), 1)  # count of rows, always count at least 1 (the object itself)
        }
        data.update(contrib)
        return data

    def stats(self, pattern=None, scale=1.0, as_dict=False, **kwargs):
        """ get statistics for all objects in the store

        Args:
            pattern (str): pattern to match object names
            scale (float): scale size statistics by this factor, defaults to 1.0 (bytes), set to 1e3 for KB, 1e6 for MB,
              1e9 for GB, etc.
            as_dict (bool): if True, return statistics as dict, else as DataFrame, defaults to False
            **kwargs:

        Returns:
            dict or DataFrame
        """
        self: OmegaStore | ObjectInformationMixin
        _stats = {}
        for meta in self.list(pattern=pattern, raw=True):
            _stats[meta.name] = self._get_collection_stats(meta.collection, scale=scale)
            _stats[meta.name].setdefault('count', 1)  # count is always at least 1 (the object itself)
            _stats[meta.name].setdefault('totalSize', 0)  # if we don't know the size, assume 0
            # TODO add gridfs file size for only this member, not gridfs overall
            # self._get_collection_stats(f'{self._fs_collection}.chunks', scale=scale)
        return _stats if as_dict else self._get_stats_dataframe(_stats)

    def dbstats(self, scale=1.0, as_dict=False, **kwargs):
        self: OmegaStore | ObjectInformationMixin
        _stats = self._get_database_stats(scale=scale)
        _stats.setdefault('fsUsedSize%', _stats.get('fsUsedSize', 0) / _stats.get('fsTotalSize', 1))
        _stats.setdefault('fsAvailableSize%', _stats.get('fsAvailableSize', 0) / _stats.get('fsTotalSize', 1))
        return _stats if as_dict else self._get_stats_dataframe(_stats, scale=scale,
                                                                index=['db'], totals='fsTotalSize')

    def _get_stats_dataframe(self, _stats, index=None, totals=None, scale=1.0):
        # transform to dataframe with totals and percentages of each statistic
        # -- index: store prefix, or 'db' for database stats
        # -- columns: count, totalSize, count%, totalSize%, ...
        # -- values: the actual values, and % values of total for each column
        import pandas as pd
        if not _stats:
            return pd.DataFrame()
        df = pd.DataFrame(_stats, index=index).T
        totals = df.sum() if totals is None else df.loc[totals].sum()
        df_pct = ((df / totals)
                  .rename(columns={k: k + '%' for k in df.columns}))
        _stats = (pd.concat([df, df_pct], axis=1))
        _stats['units'] = scale
        return _stats

    def _get_collection_stats(self, collection, scale=1.0, keys=None):
        # https://www.mongodb.com/docs/manual/reference/method/db.collection.totalSize/
        self: OmegaStore | ObjectInformationMixin
        keys = keys or ['count', 'totalSize']
        scale = self._ensure_numeric_scale(scale)
        try:
            _stats = self.mongodb.command('collstats', collection, scale=scale)
        except:
            _stats = {}
        return {
            k: _stats[k]
            for k in keys
        } if _stats else {}

    def _get_database_stats(self, scale=1.0, keys=None):
        self: OmegaStore | ObjectInformationMixin
        keys = keys or ['totalSize', 'fsUsedSize', 'fsTotalSize', 'fsAvailableSize']
        scale = self._ensure_numeric_scale(scale)
        # we calculate available size as total - used to simplify plotting code
        try:
            _stats = self.mongodb.command('dbstats', scale=scale)
            _stats['fsAvailableSize'] = _stats['fsTotalSize'] - _stats['fsUsedSize']
            # prior to 4.4, totalSize was not available
            _stats.setdefault('totalSize', _stats['dataSize'] + _stats['indexSize'])
        except:
            _stats = {'totalSize': 0, 'fsUsedSize': 0, 'fsTotalSize': 0, 'fsAvailableSize': 0}
        return {
            k: _stats[k]
            for k in keys
        }

    def _ensure_numeric_scale(self, scale):
        scale = self._scale_map.get(scale[0].lower(), scale) if isinstance(scale, str) else scale
        scale = scale if scale >= 1.0 else 1 / scale  # support 1e+-n
        return scale
