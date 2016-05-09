from uuid import uuid4

from pymongo.collection import Collection

from omegaml.store import qops
from omegaml.store.query import Filter
from omegaml.util import make_tuple
import pandas as pd


class MGrouper(object):

    """
    a Grouper for MDataFrames
    """

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

    """
    A DataFrame for mongodb

    Performs out-of-core, lazy computation on a mongodb cluster.
    Behaves like a pandas DataFrame. Actual results are returned
    as pandas DataFrames.
    """
    def __init__(self, collection, columns=None):
        self.collection = collection
        #: columns in frame
        self.columns = columns or self._get_fields()
        #: columns to sort by, defaults to not sorted
        self.sort_order = None
        #: top n documents to fetch
        self.head_limit = None
        #: top n documents to skip before returning
        self.skip_topn = None
    def __getattr__(self, attr):
        if attr in self.columns:
            return MSeries(self.collection, columns=make_tuple(attr))
        raise AttributeError(attr)
    def __getitem__(self, cols_or_slice):
        if isinstance(cols_or_slice, (list, tuple, basestring)):
            return MSeries(self.collection, columns=make_tuple(cols_or_slice))
    def groupby(self, columns):
        return MGrouper(self.collection, columns)
    def _get_fields(self):
        doc = self.collection.find_one()
        return doc.keys()
    @property
    def value(self):
        cursor = self._get_cursor()
        return self._get_dataframe_from_cursor(cursor)
    def _get_dataframe_from_cursor(self, cursor):
        """ 
        from the given cursor return a DataFrame
        """
        df = pd.DataFrame(list(cursor))
        return df.drop('_id', 1)
    def _get_cursor(self):
        cursor = self.collection.find(projection=self.columns)
        if self.sort_order:
            cursor.sort(qops.make_sortkey(make_tuple(self.sort_order)))
        if self.head_limit:
            cursor.limit(self.head_limit)
        if self.skip_topn:
            cursor.skip(self.skip_topn)
        return cursor
    def sort(self, columns):
        self.sort_order = make_tuple(columns)
        return self
    def head(self, limit):
        self.head_limit = limit
        return self
    def skip(self, topn):
        self.skip_topn = topn
        return self
    def merge(self, right, on=None, left_on=None, right_on=None,
              how='left', target=None, suffixes=('_x', '_y')):
        """
        merge this dataframe with another dataframe. only left outer joins
        are currently supported. the output is saved as a new collection,
        target name (defaults to a generated name if not specified).
        """
        # validate input
        assert how == "left", "only left merges (left outer join) are currently supported"
        for key in [on, left_on, right_on]:
            if key:
                assert isinstance(
                    key, basestring), "only single column merge keys are supported (%s)" % key
        if isinstance(right, Collection):
            right = MDataFrame(right)
        # generate lookup parameters
        right_name = self._get_collection_name_of(right, right)
        target_name = self._get_collection_name_of(
            target, '_temp.merge.%s' % uuid4().hex)
        target_field = (
            "%s_%s" % (right_name.replace('.', '_'), on or left_on))
        lookup = qops.LOOKUP(right_name,
                             key=on,
                             left_key=left_on,
                             right_key=right_on,
                             target=target_field)
        # unwind merged documents from arrays to top-level document fields
        unwind = qops.UNWIND(target_field)
        # get all fields from left, right
        project = {}
        for left_col in self.columns:
            if left_col == '_id':
                project[left_col] = 0
                continue
            project[left_col] = "$%s" % left_col
        for right_col in right.columns:
            if right_col == '_id':
                continue
            if right_col in self.columns:
                left_col = '%s%s' % (right_col, suffixes[1])
            else:
                left_col = '%s' % right_col
            project[left_col] = '$%s.%s' % (target_field, right_col)
        project = {"$project": project} 
        # store merged documents and return an MDataFrame to it
        out = qops.OUT(target_name)
        cursor = self.collection.aggregate([lookup, unwind, project, out])
        return MDataFrame(self.collection.database[target_name])
    def _get_collection_name_of(self, some, default=None):
        """
        determine the collection name of the given parameter

        returns the collection name if some is a MDataFrame, a Collection
        or a basestring. Otherwise returns default
        """
        if isinstance(some, MDataFrame):
            name = some.collection.name
        elif isinstance(some, Collection):
            name = some.name
        else:
            name = default
        return name


class MSeries(MDataFrame):

    def __init__(self, *args, **kwargs):
        super(MSeries, self).__init__(*args, **kwargs)
        self.is_unique = False
    """
    Series implementation for MDataFrames 
    
    behaves like a DataFrame but limited to one column.
    """
    def unique(self):
        self.is_unique = True
        return self
    def _get_cursor(self):
        cursor = super(MSeries, self)._get_cursor()
        if self.is_unique:
            cursor.distinct(make_tuple(self.columns)[0])
        return cursor
    @property
    def value(self):
        """
        return the value of the series

        this is a Series unless unique() was called. If unique()
        only distinct values are returned as an array, matching
        the behavior of a Series 
        """
        cursor = super(MSeries, self)._get_cursor()
        column = make_tuple(self.columns)[0]
        val = super(MSeries, self)._get_dataframe_from_cursor(cursor)[column]
        if self.is_unique:
            # this is to make sure we return the same thing as pandas
            val = val[column].unique()
        return val
