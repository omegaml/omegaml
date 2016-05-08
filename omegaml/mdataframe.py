from omegaml import Omega
from omegaml.store import qops
from omegaml.store.query import Filter
from omegaml.util import make_tuple
import pandas as pd


class MGrouper(object):

    def __init__(self, collection, columns):
        self.collection = collection
        self.columns = make_tuple(columns)
    def __getattr__(self, attr):
        if attr in self.columns:
            return MSeriesGroupby(self.collection, attr)
    def agg(self, specs):
        return self.aggregate(specs)
    def aggregate(self, specs):
        """
        aggregate by given specs

        :param specs: a dictionary of { column : function | list[functions] } 
        pairs. 
        """
        def add_stats(specs, column, stat):
            mongo_stat = stat.replace('stddev', 'stdDevSamp')
            specs['%s_%s' % (column, stat)] = {
                '$%s' % mongo_stat: '$%s' % column}
        # generate $group command
        _specs = {}
        for column, stats in specs.iteritems():
            stats = make_tuple(stats)
            for stat in stats:
                add_stats(_specs, column, stat)
        groupby = qops.GROUP(columns=self.columns,
                             **_specs)
        # execute and return a dataframe
        data = list(self.collection.aggregate([groupby]))
        for group in data:
            group.update(group.pop('_id'))
        return pd.DataFrame(data)
    def _count(self):
        return list(self.collection.aggregate([{"$group": {
            "_id": {k: "$%s" % k for k in self.columns},
            "count": {"$sum": 1}
        }}]))
    def count(self):
        """ return counts by group columns """
        counts = self._count()
        for group in counts:
            group.update(group.pop('_id'))
        return pd.DataFrame(counts).set_index(self.columns)
    def __iter__(self):
        """ for each group returns the key and a Filter object"""
        groups = self._count()
        for group in groups:
            keys = group.get('_id')
            data = Filter(self.collection, **keys)
            yield keys, data


class MSeriesGroupby(MGrouper):

    """
    like a MGrouper but limited to one column
    """
    pass


class MDataFrame(object):

    def __init__(self, collection, columns=None):
        self.collection = collection
        self.columns = columns or self._get_fields()
    def __getattr__(self, attr):
        if attr in self.columns:
            return MSeries(self.collection, columns=make_tuple(attr))
        raise AttributeError(attr)
    def __getitem__(self, cols_or_slice):
        if isinstance(cols_or_slice, (list, tuple, basestring)):
            return MDataFrame(self.collection, columns=make_tuple(cols_or_slice))
    def groupby(self, columns):
        return MGrouper(self.collection, columns)
    def _get_fields(self):
        doc = self.collection.find_one()
        return doc.keys()
    @property
    def value(self):
        df = pd.DataFrame(list(self.collection.find(projection=self.columns)))
        return df.drop('_id', 1)


class MSeries(MDataFrame):

    """
    like a DataFrame but limited to one columns
    """