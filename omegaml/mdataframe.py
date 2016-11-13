from __future__ import absolute_import

from uuid import uuid4

from numpy import isscalar
from pymongo.collection import Collection
import six

import numpy as np
from omegaml.store import qops
from omegaml.store.filtered import FilteredCollection
from omegaml.store.query import Filter, MongoQ
from omegaml.store.queryops import MongoQueryOps
from omegaml.util import make_tuple, make_list, restore_index
import pandas as pd


class MGrouper(object):

    """
    a Grouper for MDataFrames
    """
    STATS_MAP = {
        'std': 'stdDevSamp',
        'mean': 'avg',
    }

    def __init__(self, mdataframe, collection, columns, sort=True):
        self.mdataframe = mdataframe
        self.collection = collection
        self.columns = make_tuple(columns)
        self.should_sort = sort
    def __getattr__(self, attr):
        if attr in self.columns:
            return MSeriesGroupby(self, self.collection, attr)
    def agg(self, specs):
        return self.aggregate(specs)
    def aggregate(self, specs):
        """
        aggregate by given specs

        :param specs: a dictionary of { column : function | list[functions] } 
        pairs. 
        """
        def add_stats(specs, column, stat):
            specs['%s_%s' % (column, stat)] = {
                '$%s' % MGrouper.STATS_MAP.get(stat, stat): '$%s' % column}
        # generate $group command
        _specs = {}
        for column, stats in six.iteritems(specs):
            stats = make_tuple(stats)
            for stat in stats:
                add_stats(_specs, column, stat)
        groupby = qops.GROUP(columns=self.columns,
                             **_specs)
        # execute and return a dataframe
        pipeline = self._amend_pipeline([groupby])
        data = self.collection.aggregate(pipeline)
        def get_data():
            # we need this to build a pipeline for from_records
            # to process, otherwise the cursor will be exhausted already
            for group in data:
                group.update(group.pop('_id'))
                yield group
        df = pd.DataFrame.from_records(get_data())
        df = df.set_index(make_list(self.columns), drop=True)
        return df
    def _amend_pipeline(self, pipeline):
        """ amend pipeline with default ops on coll.aggregate() calls """
        if self.should_sort:
            sort = qops.SORT(**dict(qops.make_sortkey('_id')))
            pipeline.append(sort)
        return pipeline
    def _non_group_columns(self):
        """ get all columns in mdataframe that is not in columns """
        return [col for col in self.mdataframe.columns
                if col not in self.columns and col != '_id'
                and not col.startswith('_idx')]
    def _count(self):
        count_columns = self._non_group_columns()
        if len(count_columns) == 0:
            count_columns.append('_'.join(self.columns) + '_count')
        groupby = {
            "$group": {
                "_id": {k: "$%s" % k for k in self.columns},
            }
        }
        for k in count_columns:
            groupby['$group']['%s' % k] = {"$sum": 1}
        pipeline = self._amend_pipeline([groupby])
        if self.should_sort:
            sort = qops.SORT(**dict(qops.make_sortkey('_id')))
            pipeline.append(sort)
        return list(self.collection.aggregate(pipeline))
    def count(self):
        """ return counts by group columns """
        counts = self._count()
        # remove mongo object _id
        for group in counts:
            group.update(group.pop('_id'))
        # transform results to dataframe, then return as pandas would
        resultdf = pd.DataFrame(counts).set_index(make_list(self.columns),
                                                  drop=True)
        return resultdf
    def __iter__(self):
        """ for each group returns the key and a Filter object"""
        groups = self._count()
        for group in groups:
            keys = group.get('_id')
            data = Filter(self.collection, **keys)
            yield keys, data


class MLocIndexer(object):

    """
    implements the LocIndexer for MDataFrames
    """
    def __init__(self, mdataframe):
        self.mdataframe = mdataframe
    def __getitem__(self, specs):
        filterq, projection = self._get_filter(specs)
        if filterq:
            df = self.mdataframe.query(filterq)
            df.from_loc_indexer = True
        if projection:
            df = df[projection]
        return df
    def __setitem__(self, specs, value):
        raise NotImplemented
    def _get_filter(self, specs):
        filterq = []
        projection = []
        idx_cols = self.mdataframe._get_frame_index()
        specs = make_tuple(specs)
        flt_kwargs = {}
        if (isinstance(specs, (list, tuple))
                and isscalar(specs[0]) and len(idx_cols) == 1):
            # single column index with list of scalar values
            flt_kwargs['{}__in'.format(idx_cols[0])] = specs
        else:
            # list/tuple of slices or scalar values, or MultiIndex
            for i, spec in enumerate(specs):
                if i < len(idx_cols):
                    col = idx_cols[i]
                    if isinstance(spec, slice):
                        start, stop = spec.start, spec.stop
                        if start is not None:
                            flt_kwargs['{}__gte'.format(col)] = start
                        if stop is not None:
                            flt_kwargs['{}__lte'.format(col)] = stop
                    elif isscalar(col):
                        flt_kwargs[col] = spec
                else:
                    # we're out of index columns, let's look at columns
                    projection.extend(self._get_projection(spec))
        if flt_kwargs:
            filterq.append(MongoQ(**flt_kwargs))
        finalq = None
        for q in filterq:
            if finalq:
                finalq |= q
            else:
                finalq = q
        return finalq, projection
    def _get_projection(self, spec):
        columns = self.mdataframe.columns
        if np.isscalar(spec):
            return [spec]
        if isinstance(spec, (tuple, list)):
            assert all(columns.index(col) for col in columns)
            return spec
        if isinstance(spec, slice):
            start, stop = slice.start, slice.stop
            if start and not isinstance(start, int):
                start = columns.index(start)
            if stop and not isinstance(stop, int):
                # sliced ranges are inclusive
                stop = columns.index(stop) + 1
            return columns[slice(start, stop)]
        raise IndexError


class MSeriesGroupby(MGrouper):

    """
    like a MGrouper but limited to one column
    """
    def count(self):
        """
        return series count 
        """
        # MGrouper will insert a _count column, see _count(). we remove
        # that column again and return a series named as the group column
        resultdf = super(MSeriesGroupby, self).count()
        count_column = [col for col in resultdf.columns
                        if col.endswith('_count')][0]
        new_column = count_column.replace('_count', '')
        resultdf = resultdf.rename(columns={count_column: new_column})
        return resultdf[new_column]


class MDataFrame(object):

    """
    A DataFrame for mongodb

    Performs out-of-core, lazy computation on a mongodb cluster.
    Behaves like a pandas DataFrame. Actual results are returned
    as pandas DataFrames.
    """
    def __init__(self, collection, columns=None, query=None,
                 limit=None, skip=None, sort_order=None,
                 force_columns=None, **kwargs):
        self.collection = collection
        #: columns in frame
        self.columns = make_tuple(columns) if columns else self._get_fields()
        self.columns = [str(col) for col in self.columns]
        #: columns to sort by, defaults to not sorted
        self.sort_order = sort_order
        #: top n documents to fetch
        self.head_limit = limit
        #: top n documents to skip before returning
        self.skip_topn = skip
        #: filter criteria
        self.filter_criteria = query or {}
        #: force columns -- on output add columns not present
        self.force_columns = force_columns or []
        #: was this created from the loc indexer?
        self.from_loc_indexer = kwargs.get('from_loc_indexer', False)
        if self.filter_criteria:
            # make sure we have a filtered collection with the criteria given
            self.query_inplace(**self.filter_criteria)
    def __getcopy_kwargs(self, without=None):
        """ return all parameters required on a copy of this MDataFrame """
        kwargs = dict(columns=self.columns,
                      sort_order=self.sort_order,
                      limit=self.head_limit,
                      skip=self.skip_topn,
                      query=self.filter_criteria)
        [kwargs.pop(k) for k in make_tuple(without or [])]
        return kwargs
    def __getattr__(self, attr):
        if attr in self.columns:
            kwargs = self.__getcopy_kwargs()
            kwargs.update(columns=attr)
            return MSeries(self.collection, **kwargs)
        raise AttributeError(attr)
    def __getitem__(self, cols_or_slice):
        if isinstance(cols_or_slice, six.string_types):
            kwargs = self.__getcopy_kwargs()
            kwargs.update(columns=make_tuple(cols_or_slice))
            return MSeries(self.collection, **kwargs)
        elif isinstance(cols_or_slice, (tuple, list)):
            kwargs = self.__getcopy_kwargs()
            kwargs.update(columns=cols_or_slice)
            return MDataFrame(self.collection, **kwargs)
        raise ValueError('unknown accessor type %s' % type(cols_or_slice))
    def __setitem__(self, column, value):
        # True for any scalar type, numeric, bool, string
        if np.isscalar(value):
            result = self.collection.update_many(filter=self.filter_criteria,
                                                 update=qops.SET(column, value))
            self.columns.append(column)
        return self
    def groupby(self, columns, sort=True):
        return MGrouper(self, self.collection, columns, sort=sort)
    def _get_fields(self):
        doc = self.collection.find_one()
        if doc is None:
            result = []
        else:
            result = [col for col in doc.keys()
                      if col != '_id' and not col.startswith('_idx')]
        return result
    def _get_frame_index(self):
        """ return the dataframe's index columns """
        doc = self.collection.find_one()
        if doc is None:
            result = []
        else:
            result = [col for col in doc.keys()
                      if col.startswith('_idx')]
        return result
    def inspect(self, explain=False):
        """
        inspect this dataframe
        """
        if isinstance(self.collection, FilteredCollection):
            query = self.collection.query
        else:
            query = '*',
        if explain:
            explain = self._get_cursor().explain()
        return {
            'projection': self.columns,
            'query': query,
            'explain': explain or 'specify explain=True'
        }
    @property
    def value(self):
        cursor = self._get_cursor()
        df = self._get_dataframe_from_cursor(cursor)
        # this ensures the equiv. of pandas df.loc[n] is a Series
        if len(df) == 1 and self.from_loc_indexer:
            df = df.T
            df = df[df.columns[0]]
        return df

    def _get_dataframe_from_cursor(self, cursor):
        """ 
        from the given cursor return a DataFrame
        """
        df = pd.DataFrame.from_records(cursor)
        df = restore_index(df, dict())
        if '_id' in df.columns:
            df.drop('_id', axis=1, inplace=True)
        if self.force_columns:
            missing = set(self.force_columns) - set(self.columns)
            for col in missing:
                df[col] = np.NaN
        return df
    def _get_cursor(self):
        projection = make_tuple(self.columns)
        projection += make_tuple(self._get_frame_index())
        cursor = self.collection.find(projection=projection)
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
    def head(self, limit=10):
        self.head_limit = limit
        return self
    def skip(self, topn):
        self.skip_topn = topn
        return self
    def merge(self, right, on=None, left_on=None, right_on=None,
              how='inner', target=None, suffixes=('_x', '_y'),
              sort=False):
        """
        merge this dataframe with another dataframe. only left outer joins
        are currently supported. the output is saved as a new collection,
        target name (defaults to a generated name if not specified).
        """
        # validate input
        supported_how = ["left", 'inner', 'right']
        assert how in supported_how, "only %s merges are currently supported" % supported_how
        for key in [on, left_on, right_on]:
            if key:
                assert isinstance(
                    key, six.string_types), "only single column merge keys are supported (%s)" % key
        if isinstance(right, Collection):
            right = MDataFrame(right)
        assert isinstance(
            right, MDataFrame), "both must be MDataFrames, got right=%" % type(right)
        if how == 'right':
            # A right B == B left A
            return right.merge(self, on=on, left_on=right_on, right_on=left_on,
                               how='left', target=target, suffixes=suffixes)
        # generate lookup parameters
        right_name = self._get_collection_name_of(right, right)
        target_name = self._get_collection_name_of(
            target, '_temp.merge.%s' % uuid4().hex)
        target_field = (
            "%s_%s" % (right_name.replace('.', '_'), right_on or on))
        lookup = qops.LOOKUP(right_name,
                             key=on,
                             left_key=left_on,
                             right_key=right_on,
                             target=target_field)
        # unwind merged documents from arrays to top-level document fields
        unwind = qops.UNWIND(target_field, preserve=how != 'inner')
        # get all fields from left, right
        project = {}
        for left_col in self.columns:
            source_left_col = left_col
            if left_col == '_id':
                project[left_col] = 1
                continue
            if left_col.startswith('_idx'):
                continue
            if left_col != (on or left_on) and left_col in right.columns:
                left_col = '%s%s' % (left_col, suffixes[0])
            project[left_col] = "$%s" % source_left_col
        for right_col in right.columns:
            if right_col == '_id':
                continue
            if right_col.startswith('_idx'):
                continue
            if right_col == (on or right_on) and right_col == (on or left_on):
                # if the merge field is the same in both frames, we already
                # have it from left
                continue
            if right_col in self.columns:
                left_col = '%s%s' % (right_col, suffixes[1])
            else:
                left_col = '%s' % right_col
            project[left_col] = '$%s.%s' % (target_field, right_col)
        expected_columns = list(project.keys())
        project = {"$project": project}
        # store merged documents and return an MDataFrame to it
        out = qops.OUT(target_name)
        pipeline = [lookup, unwind, project]
        if sort:
            sort_cols = make_list(on or [left_on, right_on])
            sort_key = qops.make_sortkey(sort_cols)
            sort = qops.SORT(**dict(sort_key))
            pipeline.append(sort)
        pipeline.append(out)
        result = self.collection.aggregate(pipeline)
        return MDataFrame(self.collection.database[target_name],
                          force_columns=expected_columns)
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
    def _get_filter_criteria(self, *args, **kwargs):
        """ 
        return mongo query from filter specs

        this uses a Filter to produce the query from the kwargs.

        :param args: a Q object or logical combination of Q objects
        (optional)
        :param kwargs: all AND filter criteria 
        """
        if len(args) > 0:
            q = args[0]
            filter_criteria = Filter(self.collection, q).query
        else:
            filter_criteria = Filter(self.collection, **kwargs).query
        return filter_criteria
    def query_inplace(self, *args, **kwargs):
        """
        filters this MDataFrame and returns it. 

        Any subsequent operation on the dataframe will have the filter
        applied. To reset the filter call .reset() without arguments.

        :param args: a Q object or logical combination of Q objects
        (optional)
        :param kwargs: all AND filter criteria 
        :return: self
        """
        self.filter_criteria = self._get_filter_criteria(*args, **kwargs)
        self.collection = FilteredCollection(
            self.collection, query=self.filter_criteria)
        return self
    def query(self, *args, **kwargs):
        """
        return a new MDataFrame with a filter criteria

        Any subsequent operation on the new dataframe will have the filter
        applied. To reset the filter call .reset() without arguments.

        Note: Unlike pandas DataFrames, a filtered MDataFrame operates
        on the same collection as the original DataFrame

        :param args: a Q object or logical combination of Q objects
        (optional)
        :param kwargs: all AND filter criteria 
        :return: a new MDataFrame with the filter applied
        """
        filter_criteria = self._get_filter_criteria(*args, **kwargs)
        coll = FilteredCollection(self.collection, query=filter_criteria)
        return MDataFrame(coll, query=filter_criteria,
                          **self.__getcopy_kwargs(without='query'))
    def create_index(self, keys, **kwargs):
        """
        create and index the easy way
        """
        keys, kwargs = MongoQueryOps().make_index(keys)
        result = self.collection.create_index(keys, **kwargs)
        return result
    @property
    def loc(self):
        return MLocIndexer(self)


class MSeries(MDataFrame):

    """
    Series implementation for MDataFrames 

    behaves like a DataFrame but limited to one column.
    """
    def __init__(self, *args, **kwargs):
        super(MSeries, self).__init__(*args, **kwargs)
        self.is_unique = False
    def unique(self):
        self.is_unique = True
        return self
    def _get_cursor(self):
        if self.is_unique:
            # this way indexes get applied
            cursor = self.collection.distinct(make_tuple(self.columns)[0])
        else:
            cursor = super(MSeries, self)._get_cursor()
        return cursor
    @property
    def value(self):
        """
        return the value of the series

        this is a Series unless unique() was called. If unique()
        only distinct values are returned as an array, matching
        the behavior of a Series 
        """
        cursor = self._get_cursor()
        column = make_tuple(self.columns)[0]
        if self.is_unique:
            # the .distinct() cursor returns a list of values
            # this is to make sure we return the same thing as pandas
            val = [v for v in cursor]
        else:
            val = self._get_dataframe_from_cursor(cursor)
            val = val[column]
        return val
