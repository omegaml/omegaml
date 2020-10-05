from __future__ import absolute_import

import numpy as np
import pandas as pd
import six
from bson import Code
from numpy import isscalar
from pymongo.collection import Collection
from uuid import uuid4

from omegaml.store import qops
from omegaml.store.filtered import FilteredCollection
from omegaml.store.query import Filter, MongoQ
from omegaml.store.queryops import MongoQueryOps
from omegaml.util import make_tuple, make_list, restore_index, \
    cursor_to_dataframe, restore_index_columns_order, PickableCollection, extend_instance, json_normalize, ensure_index

INSPECT_CACHE = []


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

        def statfunc():
            columns = self.columns or self._non_group_columns()
            return self.agg({col: attr for col in columns})

        return statfunc

    def __getitem__(self, item):
        return self.__getattr__(item)

    def agg(self, specs):
        """
        shortcut for .aggregate
        """
        return self.aggregate(specs)

    def aggregate(self, specs, **kwargs):
        """
        aggregate by given specs

        See the following link for a list of supported operations.
        https://docs.mongodb.com/manual/reference/operator/aggregation/group/

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
        data = self.collection.aggregate(pipeline, allowDiskUse=True)

        def get_data():
            # we need this to build a pipeline for from_records
            # to process, otherwise the cursor will be exhausted already
            for group in data:
                _id = group.pop('_id')
                if isinstance(_id, dict):
                    group.update(_id)
                yield group

        df = pd.DataFrame.from_records(get_data())
        columns = make_list(self.columns)
        if columns:
            df = df.set_index(columns, drop=True)
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
                and not col.startswith('_idx')
                and not col.startswith('_om#')]

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
        return list(self.collection.aggregate(pipeline, allowDiskUse=True))

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
        # reduce count to only one column
        groups = getattr(self, self.columns[0])._count()
        for group in groups:
            keys = group.get('_id')
            data = self.mdataframe._clone(query=keys)
            yield keys, data


class MLocIndexer(object):
    """
    implements the LocIndexer for MDataFrames
    """

    def __init__(self, mdataframe, positional=False):
        self.mdataframe = mdataframe
        # if positional, any loc[spec] will be applied on the rowid only
        self.positional = positional
        # indicator will be set true if loc specs are from a range type (list, tuple, np.ndarray)
        self._from_range = False

    def __getitem__(self, specs):
        """
        access by index

        use as mdf.loc[specs] where specs is any of

        * a list or tuple of scalar index values, e.g. .loc[(1,2,3)]
        * a slice of values e.g. .loc[1:5]
        * a list of slices, e.g. .loc[1:5, 2:3]

        :return: the sliced part of the MDataFrame
        """
        filterq, projection = self._get_filter(specs)
        df = self.mdataframe
        if filterq:
            df = self.mdataframe.query(filterq)
            df.from_loc_indexer = True
            df.from_loc_range = self._from_range
        if projection:
            df = df[projection]
        if isinstance(self.mdataframe, MSeries):
            df = df._as_mseries(df.columns[0])
        if getattr(df, 'immediate_loc', False):
            df = df.value
        return df

    def __setitem__(self, specs, value):
        raise NotImplementedError()

    def _get_filter(self, specs):
        filterq = []
        projection = None
        if self.positional:
            idx_cols = ['_om#rowid']
        else:
            idx_cols = self.mdataframe._get_frame_index()
        flt_kwargs = {}
        enumerable_types = (list, tuple, np.ndarray)
        if isinstance(specs, np.ndarray):
            specs = specs.tolist()
        if (isinstance(specs, enumerable_types)
              and isscalar(specs[0]) and len(idx_cols) == 1
              and not any(isinstance(s, slice) for s in specs)):
            # single column index with list of scalar values
            if (self.positional and isinstance(specs, tuple) and len(specs) == 2
                  and all(isscalar(v) for v in specs)):
                # iloc[int, int] is a cell access
                flt_kwargs[idx_cols[0]] = specs[0]
                projection = self._get_projection(specs[1])
            else:
                flt_kwargs['{}__in'.format(idx_cols[0])] = specs
                self._from_range = True
        elif isinstance(specs, (int, str)):
            flt_kwargs[idx_cols[0]] = specs
        else:
            specs = make_tuple(specs)
            # list/tuple of slices or scalar values, or MultiIndex
            for i, spec in enumerate(specs):
                if i < len(idx_cols):
                    col = idx_cols[i]
                    if isinstance(spec, slice):
                        self._from_range = True
                        start, stop = spec.start, spec.stop
                        if start is not None:
                            flt_kwargs['{}__gte'.format(col)] = start
                        if stop is not None:
                            if isinstance(stop, int):
                                stop -= int(self.positional)
                            flt_kwargs['{}__lte'.format(col)] = stop
                    elif isinstance(spec, enumerable_types) and isscalar(spec[0]):
                        self._from_range = True
                        # single column index with list of scalar values
                        # -- convert to list for PyMongo serialization
                        if isinstance(spec, np.ndarray):
                            spec = spec.tolist()
                        flt_kwargs['{}__in'.format(col)] = spec
                    elif isscalar(col):
                        flt_kwargs[col] = spec
                else:
                    # we're out of index columns, let's look at columns
                    cur_proj = self._get_projection(spec)
                    # if we get a single column, that's the projection
                    # if we had a single column, now need to add more, create a list
                    # if we have a list already, extend that
                    if projection is None:
                        projection = cur_proj
                    elif isinstance(projection, list):
                        projection.extend(cur_proj)
                    else:
                        projection = [projection, cur_proj]
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
            start, stop = spec.start, spec.stop
            if all(isinstance(v, int) for v in (start, stop)):
                start, stop, step = spec.indices(len(columns))
            else:
                start = columns.index(start) if start is not None else 0
                stop = columns.index(stop) + 1 if stop is not None else len(columns)
            return columns[slice(start, stop)]
        raise IndexError


class MPosIndexer(MLocIndexer):
    """
    implements the position-based indexer for MDataFrames
    """

    def __init__(self, mdataframe):
        super(MPosIndexer, self).__init__(mdataframe, positional=True)

    def _get_projection(self, spec):
        columns = self.mdataframe.columns
        if np.isscalar(spec):
            return columns[spec]
        if isinstance(spec, (tuple, list)):
            return [col for i, col in enumerate(spec) if i in spec]
        if isinstance(spec, slice):
            start, stop = slice.start, slice.stop
            if start and not isinstance(start, int):
                start = 0
            if stop and not isinstance(stop, int):
                # sliced ranges are inclusive
                stop = len(columns)
            return columns[slice(start, stop)]
        raise IndexError


class MSeriesGroupby(MGrouper):
    """
    like a MGrouper but limited to one column
    """

    def count(self):
        """
        return series count

        :return: counts by group
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

    Performs out-of-core, lazy computOation on a mongodb cluster.
    Behaves like a pandas DataFrame. Actual results are returned
    as pandas DataFrames.
    """

    STATFUNCS = ['mean', 'std', 'min', 'max', 'sum', 'var']

    def __init__(self, collection, columns=None, query=None,
                 limit=None, skip=None, sort_order=None,
                 force_columns=None, immediate_loc=False, auto_inspect=False,
                 normalize=False, raw=False,
                 parser=None,
                 preparefn=None, from_loc_range=False, **kwargs):
        self.collection = PickableCollection(collection)
        # columns in frame
        self.columns = make_tuple(columns) if columns else self._get_fields(raw=raw)
        self.columns = [str(col) for col in self.columns]
        # columns to sort by, defaults to not sorted
        self.sort_order = sort_order
        # top n documents to fetch
        self.head_limit = limit
        # top n documents to skip before returning
        self.skip_topn = skip
        # filter criteria
        self.filter_criteria = query or {}
        # force columns -- on output add columns not present
        self.force_columns = force_columns or []
        # was this created from the loc indexer?
        self.from_loc_indexer = kwargs.get('from_loc_indexer', False)
        # was the loc index used a range? Else a single value
        self.from_loc_range = from_loc_range
        # setup query for filter criteries, if provided
        if self.filter_criteria:
            # make sure we have a filtered collection with the criteria given
            if isinstance(self.filter_criteria, dict):
                self.query_inplace(**self.filter_criteria)
            elif isinstance(self.filter_criteria, Filter):
                self.query_inplace(self.filter_criteria)
            else:
                raise ValueError('Invalid query specification of type {}'.format(type(self.filter_criteria)))
        # if immediate_loc is True, .loc and .iloc always evaluate
        self.immediate_loc = immediate_loc
        # __array__ will return this value if it is set, set it otherwise
        self._evaluated = None
        # set true to automatically capture inspects on .value. retrieve using .inspect(cached=True)
        self.auto_inspect = auto_inspect
        self._inspect_cache = INSPECT_CACHE
        # apply mixins
        self._applyto = str(self.__class__)
        self._apply_mixins()
        # parser to parse documents to dataframe
        self._parser = json_normalize if normalize else parser
        # prepare function to be applied just before returning from .value
        self._preparefn = preparefn
        # keep technical fields like _id, _idx etc
        self._raw = raw

    def _apply_mixins(self, *args, **kwargs):
        """
        apply mixins in defaults.OMEGA_MDF_MIXINS
        """
        from omegaml import settings
        defaults = settings()
        for mixin, applyto in defaults.OMEGA_MDF_MIXINS:
            if any(v in self._applyto for v in applyto.split(',')):
                extend_instance(self, mixin, *args, **kwargs)

    def __getstate__(self):
        # pickle support. note that the hard work is done in PickableCollection
        data = dict(self.__dict__)
        data.update(_evaluated=None)
        data.update(_inspect_cache=None)
        data.update(auto_inspect=self.auto_inspect)
        data.update(_preparefn=self._preparefn)
        data.update(_parser=self._parser)
        data.update(_raw=self._raw)
        data.update(collection=self.collection)
        return data

    def __reduce__(self):
        state = self.__getstate__()
        args = self.collection,
        return _mdf_remake, args, state

    def __setstate__(self, state):
        # pickle support. note that the hard work is done in PickableCollection
        for k, v in state.items():
            setattr(self, k, v)

    def _getcopy_kwargs(self, without=None):
        """ return all parameters required on a copy of this MDataFrame """
        kwargs = dict(columns=self.columns,
                      sort_order=self.sort_order,
                      limit=self.head_limit,
                      skip=self.skip_topn,
                      from_loc_indexer=self.from_loc_indexer,
                      from_loc_range=self.from_loc_range,
                      immediate_loc=self.immediate_loc,
                      query=self.filter_criteria,
                      auto_inspect=self.auto_inspect,
                      preparefn=self._preparefn)
        [kwargs.pop(k) for k in make_tuple(without or [])]
        return kwargs

    def __array__(self, dtype=None):
        # FIXME inefficient. make MDataFrame a drop-in replacement for any numpy ndarray
        # this evaluates every single time
        if self._evaluated is None:
            self._evaluated = array = self.value.values
        else:
            array = self._evaluated
        return array

    def __getattr__(self, attr):
        if attr in MDataFrame.STATFUNCS:
            return self.statfunc(attr)
        if attr in self.columns:
            kwargs = self._getcopy_kwargs()
            kwargs.update(columns=attr)
            return MSeries(self.collection, **kwargs)
        raise AttributeError(attr)

    def __getitem__(self, cols_or_slice):
        """
        select and project by column, columns, slice, masked-style filter

        Masked-style filters work similar to pd.DataFrame/Series masks
        but do not actually return masks but an instance of Filter. A
        Filter is a delayed evaluation on the data frame.

            # select all rows where any column is == 5
            mdf = MDataFrame(coll)
            flt = mdf == 5
            mdf[flt]
            =>

        :param cols_or_slice: single column (str), multi-columns (list),
          slice to select columns or a masked-style
        :return: filtered MDataFrame or MSeries
        """
        if isinstance(cols_or_slice, six.string_types):
            # column name => MSeries
            return self._as_mseries(cols_or_slice)
        elif isinstance(cols_or_slice, int):
            # column number => MSeries
            column = self.columns[cols_or_slice]
            return self._as_mseries(column)
        elif isinstance(cols_or_slice, (tuple, list)):
            # list of column names => MDataFrame subset on columns
            kwargs = self._getcopy_kwargs()
            kwargs.update(columns=cols_or_slice)
            return MDataFrame(self.collection, **kwargs)
        elif isinstance(cols_or_slice, Filter):
            kwargs = self._getcopy_kwargs()
            kwargs.update(query=cols_or_slice.query)
            return MDataFrame(self.collection, **kwargs)
        elif isinstance(cols_or_slice, np.ndarray):
            return self.iloc[cols_or_slice]
        raise ValueError('unknown accessor type %s' % type(cols_or_slice))

    def __setitem__(self, column, value):
        # True for any scalar type, numeric, bool, string
        if np.isscalar(value):
            result = self.collection.update_many(filter=self.filter_criteria,
                                                 update=qops.SET(column, value))
            self.columns.append(column)
        return self

    def _clone(self, collection=None, **kwargs):
        # convenience method to clone itself with updates
        return self.__class__(collection or self.collection, **kwargs,
                              **self._getcopy_kwargs(without=list(kwargs.keys())))

    def statfunc(self, stat):
        aggr = MGrouper(self, self.collection, [], sort=False)
        return getattr(aggr, stat)

    def groupby(self, columns, sort=True):
        """
        Group by a given set of columns

        :param columns: the list of columns
        :param sort: if True sort by group key
        :return: MGrouper
        """
        return MGrouper(self, self.collection, columns, sort=sort)

    def _get_fields(self, raw=False):
        result = []
        doc = self.collection.find_one()
        if doc is not None:
            if raw:
                result = list(doc.keys())
            else:
                result = [str(col) for col in doc.keys()
                          if col != '_id'
                          and not col.startswith('_idx')
                          and not col.startswith('_om#')]
        return result

    def _get_frame_index(self):
        """ return the dataframe's index columns """
        doc = self.collection.find_one()
        if doc is None:
            result = []
        else:
            result = restore_index_columns_order(doc.keys())
        return result

    def _get_frame_om_fields(self):
        """ return the dataframe's omega special fields columns """
        doc = self.collection.find_one()
        if doc is None:
            result = []
        else:
            result = [k for k in list(doc.keys()) if k.startswith('_om#')]
        return result

    def _as_mseries(self, column):
        kwargs = self._getcopy_kwargs()
        kwargs.update(columns=make_tuple(column))
        return MSeries(self.collection, **kwargs)

    def inspect(self, explain=False, cached=False, cursor=None, raw=False):
        """
        inspect this dataframe's actual mongodb query

        :param explain: if True explains access path
        """
        if not cached:
            if isinstance(self.collection, FilteredCollection):
                query = self.collection.query
            else:
                query = '*',
            if explain:
                cursor = cursor or self._get_cursor()
                explain = cursor.explain()
            data = {
                'projection': self.columns,
                'query': query,
                'explain': explain or 'specify explain=True'
            }
        else:
            data = self._inspect_cache
        if not (raw or explain):
            data = pd.DataFrame(json_normalize(data))
        return data

    def count(self):
        """
        projected number of rows when resolving
        """
        counts = pd.Series({
            col: len(self)
            for col in self.columns}, index=self.columns)
        return counts

    def __len__(self):
        """
        the projected number of rows when resolving
        """
        return self._get_cursor().count()

    @property
    def shape(self):
        """
        return shape of dataframe
        """
        return len(self), len(self.columns)

    @property
    def ndim(self):
        return len(self.shape)

    @property
    def value(self):
        """
        resolve the query and return a Pandas DataFrame

        :return: the result of the query as a pandas DataFrame
        """
        cursor = self._get_cursor()
        df = self._get_dataframe_from_cursor(cursor)
        if self.auto_inspect:
            self._inspect_cache.append(self.inspect(explain=True, cursor=cursor, raw=True))
        # this ensures the equiv. of pandas df.loc[n] is a Series
        if self.from_loc_indexer:
            if len(df) == 1 and not self.from_loc_range:
                idx = df.index
                df = df.T
                df = df[df.columns[0]]
                if df.ndim == 1 and len(df) == 1 and not isinstance(idx, pd.MultiIndex):
                    # single row single dimension, numeric index only
                    df = df.iloc[0]
            elif (df.ndim == 1 or df.shape[1] == 1) and not self.from_loc_range:
                df = df[df.columns[0]]
        if self._preparefn:
            df = self._preparefn(df)
        return df

    def reset(self):
        # TODO if head(), tail(), query(), .loc/iloc should return a new MDataFrame instance to avoid having a reset need
        self.head_limit = None
        self.skip_topn = None
        self.filter_criteria = {}
        self.force_columns = []
        self.sort_order = None
        self.from_loc_indexer = False
        return self

    def _get_dataframe_from_cursor(self, cursor):
        """
        from the given cursor return a DataFrame
        """
        df = cursor_to_dataframe(cursor, parser=self._parser)
        df = self._restore_dataframe_proper(df)
        return df

    def _restore_dataframe_proper(self, df):
        df = restore_index(df, dict())
        if '_id' in df.columns and not self._raw:
            df.drop('_id', axis=1, inplace=True)
        if self.force_columns:
            missing = set(self.force_columns) - set(self.columns)
            for col in missing:
                df[col] = np.NaN
        return df

    def _get_cursor(self):
        projection = make_tuple(self.columns)
        projection += make_tuple(self._get_frame_index())
        if not self.sort_order:
            # implicit sort
            projection += make_tuple(self._get_frame_om_fields())
        cursor = self.collection.find(projection=projection)
        if self.sort_order:
            cursor.sort(qops.make_sortkey(make_tuple(self.sort_order)))
        if self.head_limit:
            cursor.limit(self.head_limit)
        if self.skip_topn:
            cursor.skip(self.skip_topn)
        return cursor

    def sort(self, columns):
        """
        sort by specified columns

        :param columns: str of single column or a list of columns. Sort order
                        is specified as the + (ascending) or - (descending)
                        prefix to the column name. Default sort order is
                        ascending.
        :return: the MDataFrame
        """
        self._evaluated = None
        self.sort_order = make_tuple(columns)
        return self

    def head(self, limit=10):
        """
        return up to limit numbers of rows

        :param limit: the number of rows to return. Defaults to 10
        :return: the MDataFrame
        """
        return self._clone(limit=limit)

    def tail(self, limit=10):
        """
        return up to limit number of rows from last inserted values

        :param limit:
        :return:
        """
        tail_n = self.skip(len(self) - limit)
        return self._clone(skip=tail_n)

    def skip(self, topn):
        """
        skip the topn number of rows

        :param topn: the number of rows to skip.
        :return: the MDataFrame
        """
        return self._clone(skip=topn)

    def merge(self, right, on=None, left_on=None, right_on=None,
              how='inner', target=None, suffixes=('_x', '_y'),
              sort=False, inspect=False, filter=None):
        """
        merge this dataframe with another dataframe. only left outer joins
        are currently supported. the output is saved as a new collection,
        target name (defaults to a generated name if not specified).

        :param right: the other MDataFrame
        :param on: the list of key columns to merge by
        :param left_on: the list of the key columns to merge on this dataframe
        :param right_on: the list of the key columns to merge on the other
           dataframe
        :param how: the method to merge. supported are left, inner, right.
           Defaults to inner
        :param target: the name of the collection to store the merge results
           in. If not provided a temporary name will be created.
        :param suffixes: the suffixes to apply to identical left and right
           columns
        :param sort: if True the merge results will be sorted. If False the
           MongoDB natural order is implied.
        :returns: the MDataFrame to the target MDataFrame
        """
        # validate input
        supported_how = ["left", 'inner', 'right']
        assert how in supported_how, "only %s merges are currently supported" % supported_how
        for key in [on, left_on, right_on]:
            if key:
                assert isinstance(
                    key, six.string_types), "only single column merge keys are supported (%s)" % key
        if isinstance(right, (Collection, PickableCollection, FilteredCollection)):
            right = MDataFrame(right)
        assert isinstance(
            right, MDataFrame), "both must be MDataFrames, got right=%" % type(right)
        if how == 'right':
            # A right B == B left A
            return right.merge(self, on=on, left_on=right_on, right_on=left_on,
                               how='left', target=target, suffixes=suffixes)
        # generate lookup parameters
        on = on or '_id'
        right_name = self._get_collection_name_of(right, right)
        target_name = self._get_collection_name_of(
            target, '_temp.merge.%s' % uuid4().hex)
        target_field = (
              "%s_%s" % (right_name.replace('.', '_'), right_on or on))
        """
        TODO enable filter criteria on right dataframe. requires changing LOOKUP syntax from 
             equitly to arbitray match 
        
        if right.filter_criteria:
            right_filter = [qops.MATCH(self._get_filter_criteria(**right.filter_criteria))]
        else:
            right_filter = None
        """
        right_filter = None
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
            if left_col.startswith('_om#'):
                continue
            if left_col != (on or left_on) and left_col in right.columns:
                left_col = '%s%s' % (left_col, suffixes[0])
            project[left_col] = "$%s" % source_left_col
        for right_col in right.columns:
            if right_col == '_id':
                continue
            if right_col.startswith('_idx'):
                continue
            if right_col.startswith('_om#'):
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
        if '_id' not in project:
            project['_id'] = 0  # never copy objectids to avoid duplicate keys, unless requested
        project = {"$project": project}
        # store merged documents and return an MDataFrame to it
        out = qops.OUT(target_name)
        pipeline = [lookup, unwind, project]
        if filter:
            query = qops.MATCH(self._get_filter_criteria(**filter))
            pipeline.append(query)
        if sort:
            sort_cols = make_list(on or [left_on, right_on])
            sort_key = qops.make_sortkey(sort_cols)
            sort = qops.SORT(**dict(sort_key))
            pipeline.append(sort)
        pipeline.append(out)
        if inspect:
            result = pipeline
        else:
            result = self.collection.aggregate(pipeline, allowDiskUse=True)
            result = MDataFrame(self.collection.database[target_name],
                                force_columns=expected_columns)
        return result

    def append(self, other):
        if isinstance(other, Collection):
            right = MDataFrame(other)
        assert isinstance(
            other, MDataFrame), "both must be MDataFrames, got other={}".format(type(other))
        outname = self.collection.name
        mrout = {
            'merge': outname,
            'nonAtomic': True,
        }
        mapfn = Code("""
        function() {
           this._id = ObjectId();
           if(this['_om#rowid']) {
              this['_om#rowid'] += %s;
           }
           emit(this._id, this);
        }
        """ % len(self))
        reducefn = Code("""
        function(key, value) {
           return value;
        }
        """)
        finfn = Code("""
        function(key, value) {
           return value;
        }
        """)
        other.collection.map_reduce(mapfn, reducefn, mrout, finalize=finfn, jsMode=True)
        unwind = {
            "$replaceRoot": {
                "newRoot": {
                    "$ifNull": ["$value", "$$CURRENT"],
                }
            }
        }
        output = qops.OUT(outname)
        pipeline = [unwind, output]
        self.collection.aggregate(pipeline, allowDiskUse=True)
        return self

    def _get_collection_name_of(self, some, default=None):
        """
        determine the collection name of the given parameter

        returns the collection name if some is a MDataFrame, a Collection
        or a string_type. Otherwise returns default
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
            if isinstance(q, MongoQ):
                filter_criteria = Filter(self.collection, q).query
            elif isinstance(q, Filter):
                filter_criteria = Filter(self.collection, q.q).query
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
        self._evaluated = None
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
        effective_filter = dict(self.filter_criteria)
        filter_criteria = self._get_filter_criteria(*args, **kwargs)
        if '$and' in effective_filter:
            effective_filter['$and'].extend(filter_criteria.get('$and'))
        else:
            effective_filter.update(filter_criteria)
        coll = FilteredCollection(self.collection, query=effective_filter)
        return self._clone(collection=coll, query=effective_filter)

    def create_index(self, keys, **kwargs):
        """
        create and index the easy way
        """
        keys, kwargs = MongoQueryOps().make_index(keys)
        result = ensure_index(self.collection, keys, **kwargs)
        return result

    def list_indexes(self):
        """
        list all indices in database
        """
        return cursor_to_dataframe(self.collection.list_indexes())

    def iterchunks(self, chunksize=100):
        """
        return an iterator

        Args:
            chunksize (int): number of rows in each chunk

        Returns:
            a dataframe of max. length chunksize
        """
        chunksize = int(chunksize)
        i = 0
        while True:
            chunkdf = self.skip(i).head(chunksize).value
            if len(chunkdf) == 0:
                break
            i += chunksize
            yield chunkdf

    def itertuples(self, chunksize=1000):
        chunksize = int(chunksize)
        __doc__ = pd.DataFrame.itertuples.__doc__

        for chunkdf in self.iterchunks(chunksize=chunksize):
            for row in chunkdf.iterrows():
                yield row

    def iterrows(self, chunksize=1000):
        chunksize = int(chunksize)
        __doc__ = pd.DataFrame.iterrows.__doc__

        for chunkdf in self.iterchunks(chunksize=chunksize):
            if isinstance(chunkdf, pd.DataFrame):
                for row in chunkdf.iterrows():
                    yield row
            else:
                # Series does not have iterrows
                for i in range(0, len(chunkdf), chunksize):
                    yield chunkdf.iloc[i:i+chunksize]

    def iteritems(self):
        __doc__ = pd.DataFrame.iteritems.__doc__
        return self.items()

    def items(self):
        __doc__ = pd.DataFrame.items.__doc__

        for col in self.columns:
            yield col, self[col].value

    @property
    def loc(self):
        """
        Access by index

        Use as mdf.loc[index_value]

        :return: MLocIndexer
        """
        self._evaluated = None
        indexer = MLocIndexer(self)
        return indexer

    @property
    def iloc(self):
        self._evaluated = None
        indexer = MPosIndexer(self)
        return indexer

    def rows(self, start=None, end=None, chunksize=1000):
        # equivalent to .iloc[start:end].iteritems(),
        start, end, chunksize = (int(v) for v in (start, end, chunksize))
        return self.iloc[slice(start, end)].iterchunks(chunksize)


    def __repr__(self):
        kwargs = ', '.join('{}={}'.format(k, v) for k, v in six.iteritems(self._getcopy_kwargs()))
        return "MDataFrame(collection={collection.name}, {kwargs})".format(collection=self.collection,
                                                                           kwargs=kwargs)


class MSeries(MDataFrame):
    """
    Series implementation for MDataFrames

    behaves like a DataFrame but limited to one column.
    """

    def __init__(self, *args, **kwargs):
        super(MSeries, self).__init__(*args, **kwargs)
        # true if only unique values apply
        self.is_unique = False
        # apply mixins
        self._applyto = str(self.__class__)
        self._apply_mixins(*args, **kwargs)

    def __getitem__(self, cols_or_slice):
        if isinstance(cols_or_slice, Filter):
            return MSeries(self.collection, columns=self.columns,
                           query=cols_or_slice.query)
        return super(MSeries, self).__getitem__(cols_or_slice)

    @property
    def name(self):
        return self.columns[0]

    def unique(self):
        """
        return the unique set of values for the series

        :return: MSeries
        """
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

        :return: pandas.Series
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
            val.name = self.name
            if len(val) == 1 and self.from_loc_indexer:
                val = val.iloc[0]
        if self.auto_inspect:
            self._inspect_cache.append(self.inspect(explain=True, cursor=cursor, raw=True))
        if self._preparefn:
            df = self._preparefn(val)
        return val

    def __repr__(self):
        kwargs = ', '.join('{}={}'.format(k, v) for k, v in six.iteritems(self._getcopy_kwargs()))
        return "MSeries(collection={collection.name}, {kwargs})".format(collection=self.collection,
                                                                        kwargs=kwargs)

    @property
    def shape(self):
        return len(self),


def _mdf_remake(collection):
    # recreate a pickled MDF
    mdf = MDataFrame(collection)
    return mdf
