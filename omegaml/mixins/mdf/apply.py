import hashlib
import json
import pandas as pd
import six
from itertools import product
from uuid import uuid4

from omegaml.documents import make_QueryCache
from omegaml.mdataframe import MDataFrame, MSeries
from omegaml.store import qops
from omegaml.store.filtered import FilteredCollection
from omegaml.util import make_tuple, extend_instance


class ApplyMixin(object):
    """
    Implements the apply() mixin supporting arbitrary functions to build aggregation pipelines

    Note that .apply() does not execute immediately. Instead it builds an aggregation pipeline
    that is executed on MDataFrame.value. Note that .apply() calls cannot be cascaded yet, i.e.
    a later .apply() will override a previous.apply().

    See ApplyContext for usage examples.
    """

    def __init__(self, *args, **kwargs):
        super(ApplyMixin, self).__init__(*args, **kwargs)
        self._init_mixin(*args, **kwargs)

    def _init_mixin(self, *args, **kwargs):
        self.apply_fn = kwargs.get('apply_fn', None)
        # set to True if the pipeline is a facet operation
        self.is_from_facet = kwargs.get('is_from_facet', False)
        # index columns
        self.index_columns = kwargs.get('index_columns', [])
        # db alias
        self._db_alias = kwargs.get('db_alias', self._ensure_db_connection())
        # cache used on persist()
        self.cache = kwargs.get('cache', ApplyCache(self._db_alias))

    def _ensure_db_connection(self):
        from mongoengine.connection import _dbs, _connections

        seek_db = self.collection.database
        for alias, db in _dbs.items():
            if db is seek_db:
                self._db_alias = alias
                break
        else:
            # fake connection register
            alias = self._db_alias = 'omega-{}'.format(uuid4().hex)
            _connections[alias] = seek_db.client
            _dbs[alias] = seek_db
        return self._db_alias

    def nocache(self):
        self.cache = None
        return self

    def reset_cache(self, full=False):
        """
        Reset the apply cache

        :param full: if True will reset all caches for the collection, if False will only remove
            the cache for the specific .apply operations
        :return:
        """
        QueryCache = make_QueryCache(db_alias=self._db_alias)
        if full:
            QueryCache.objects.filter(value__collection=self.collection.name).delete()
        else:
            pipeline = self._build_pipeline()
            key = self._make_cache_key(self.collection, pipeline)
            QueryCache.objects.filter(key=key).delete()
        return self

    def _make_cache_key(self, collection, pipeline):
        # remove random output value
        if '$out' in pipeline[-1] and pipeline[-1]['$out'].startswith('cache'):
            pipeline = list(pipeline)[:-1]
        spipeline = json.dumps(pipeline, sort_keys=True)
        data = '{}_{}'.format(collection.name, spipeline).encode('utf-8')
        key = hashlib.md5(data).hexdigest()
        return key

    def _getcopy_kwargs(self, **kwargs):
        kwargs = super(ApplyMixin, self)._getcopy_kwargs(**kwargs)
        kwargs.update(is_from_facet=self.is_from_facet,
                      index_columns=self.index_columns,
                      cache=self.cache,
                      apply_fn=self.apply_fn)
        return kwargs

    def noapply(self):
        self.apply_fn = None
        return self

    def apply(self, fn, inplace=False, preparefn=None):
        if inplace:
            obj = self
        else:
            kwargs = self._getcopy_kwargs()
            kwargs.update(preparefn=preparefn)
            if isinstance(self, MSeries):
                obj = MSeries(self.collection, **kwargs)
            else:
                obj = MDataFrame(self.collection, **kwargs)
        obj.apply_fn = fn
        return obj

    def persist(self):
        """
        Execute and store results in cache

        Any pipeline of the same operations, in the same order, on
        the same collection will return the same result.
        """
        # generate a cache key
        pipeline = self._build_pipeline()
        key = self._make_cache_key(self.collection, pipeline)
        outname = 'cache_{}'.format(uuid4().hex)
        value = {
            'collection': self.collection.name,
            'result': outname,
        }
        # do usual processing, store result
        # -- note we pass pipeline to avoid processing iterators twice
        pipeline.append({
            '$out': outname,
        })
        cursor = self._get_cursor(pipeline=pipeline, use_cache=False)
        # consume cursor to store output (via $out)
        for v in cursor:
            pass
        # set cache
        self.cache.set(key, value)
        return key

    def set_index(self, columns):
        self.index_columns = make_tuple(columns)
        return self

    def inspect(self, explain=False, *args, **kwargs):
        if self.apply_fn:
            details = {
                'pipeline': self._build_pipeline()
            }
            if explain:
                details.update(self.__dict__)
            return details
        return super(ApplyMixin, self).inspect(*args, explain=explain, **kwargs)

    def _execute(self):
        ctx = ApplyContext(self, columns=self.columns)
        try:
            result = self.apply_fn(ctx)
        except Exception as e:
            msg = [repr(stage) for stage in ctx.stages] + [repr(e)]
            raise RuntimeError(msg)
        if result is None or isinstance(result, ApplyContext):
            result = result or ctx
            self.index_columns = self.index_columns or result.index_columns
            return result
        elif isinstance(result, list):
            return result
        elif isinstance(result, dict):
            # expect a mapping of col=ApplyContext each with its own list of stages
            # -- build a combined context by adding each expression
            #    this ensures any multi-stage projections are carried forward
            facets = {}
            for col, expr in six.iteritems(result):
                if isinstance(expr, ApplyContext):
                    facets[col] = list(expr)
                    project = {
                        '$project': {
                            col: '$' + expr.columns[0]
                        },
                    }
                    facets[col].append(project)
                else:
                    facets[col] = expr
            facet = {
                '$facet': facets
            }
            self.is_from_facet = True
            return [facet]
        raise ValueError('Cannot build pipeline from apply result of type {}'.format(type(result)))

    def _build_pipeline(self):
        pipeline = []
        stages = self._execute()
        pipeline.extend(stages)
        self._amend_pipeline(pipeline)
        return pipeline

    def _amend_pipeline(self, pipeline):
        """ amend pipeline with default ops on coll.aggregate() calls """
        if self.sort_order:
            sort = qops.SORT(**dict(qops.make_sortkey(self.sort_order)))
            pipeline.append(sort)
        return pipeline

    def _get_cached_cursor(self, pipeline=None, use_cache=True):
        pipeline = pipeline or self._build_pipeline()
        if use_cache and self.cache:
            key = self._make_cache_key(self.collection, pipeline)
            entry = self.cache.get(key)
            if entry is not None:
                # read result
                outname = entry.value['result']
                return self.collection.database[outname].find()

    def _get_cursor(self, pipeline=None, use_cache=True):
        # for apply functions, call the apply function, expecting a pipeline in return
        if self.apply_fn:
            pipeline = pipeline or self._build_pipeline()
            cursor = self._get_cached_cursor(pipeline=pipeline, use_cache=use_cache)
            if cursor is None:
                filter_criteria = self._get_filter_criteria()
                cursor = FilteredCollection(self.collection).aggregate(pipeline, filter=filter_criteria, allowDiskUse=True)
        else:
            cursor = super(ApplyMixin, self)._get_cursor()
        return cursor

    def _get_dataframe_from_cursor(self, cursor):
        df = super(ApplyMixin, self)._get_dataframe_from_cursor(cursor)
        if self.is_from_facet:
            # if this was from a facet pipeline (i.e. multi-column mapping), combine
            # $facet returns one document for each stage.
            frames = []
            for col in df.columns:
                coldf = pd.DataFrame(df[col].iloc[0]).set_index('_id')
                frames.append(coldf)
            df = pd.concat(frames, axis=1).reset_index()
            df = self._restore_dataframe_proper(df)
        # TODO write a unit test for this condition
        if self.index_columns and all(col in df.columns for col in self.index_columns):
            df.set_index(self.index_columns, inplace=True)
        return df


class ApplyContext(object):
    """
    Enable apply functions

    .apply(fn) will call fn(ctx) where ctx is an ApplyContext.
    The context supports methods to apply functions in a Pandas-style apply manner. ApplyContext is extensible
    by adding an extension class to defaults.OMEGA_MDF_APPLY_MIXINS.

    Note that unlike a Pandas DataFrame, ApplyContext does not itself contain any data.
    Rather it is part of an expression tree, i.e. the aggregation pipeline. Thus any
    expressions applied are translated into operations on the expression tree. The expression
    tree is evaluated on MDataFrame.value, at which point the ApplyContext nor the function
    that created it are active.

    Examples::

        mdf.apply(lambda v: v * 5 ) => multiply every column in dataframe
        mdf.apply(lambda v: v['foo'].dt.week) => get week of date for column foo
        mdf.apply(lambda v: dict(a=v['foo'].dt.week,
                                 b=v['bar'] * 5) => run multiple pipelines and get results

        The callable passed to apply can be any function. It can either return None,
        the context passed in or a list of pipeline stages.

        # apply any of the below functions
        mdf.apply(customfn)

        # same as lambda v: v.dt.week
        def customfn(ctx):
            return ctx.dt.week

        # simple pipeline
        def customfn(ctx):
            ctx.project(x={'$multiply: ['$x', 5]})
            ctx.project(y={'$divide: ['$x', 2]})

        # complex pipeline
        def customfn(ctx):
            return [
                { '$match': ... },
                { '$project': ... },
            ]
    """

    def __init__(self, caller, columns=None, index=None):
        self.caller = caller
        self.columns = columns
        self.index_columns = index or []
        self.computed = []
        self.stages = []
        self.expressions = []
        self._apply_mixins()

    def _apply_mixins(self):
        """
        apply mixins in defaults.OMEGA_MDF_APPLY_MIXINS
        """
        from omegaml import settings
        defaults = settings()
        for mixin, applyto in defaults.OMEGA_MDF_APPLY_MIXINS:
            if any(v in self.caller._applyto for v in applyto.split(',')):
                extend_instance(self, mixin)

    def __iter__(self):
        # return pipeline stages
        for stage in self.stages:
            if isinstance(stage, ApplyContext):
                for sub_stage in stage:
                    yield sub_stage
            else:
                yield stage

    def __getitem__(self, sel):
        """
        return a stage subset on a column
        """
        subctx = ApplyContext(self.caller, columns=make_tuple(sel), index=self.index_columns)
        self.add(subctx)
        return subctx

    def __setitem__(self, sel, val):
        """
        add a projection to a sub context

        ctx['col'] = value-expression
        """
        mapping = {
            col: v
            for (col, v) in zip(make_tuple(sel), make_tuple(val))}
        self.project(mapping)

    def __repr__(self):
        return 'ApplyContext(stages={}, expressions={})'.format(self.stages, self.expressions)

    def add(self, stage):
        """
        Add a processing stage to the pipeline

        see https://docs.mongodb.com/manual/meta/aggregation-quick-reference/
        """
        self.stages.append(stage)
        return self

    def project_keeper_columns(self):
        # keep index, computed
        index = {
            col: '$' + col
            for col in self.index_columns}
        computed = {
            col: '$' + col
            for col in self.computed}
        keep = {}
        keep.update(index)
        keep.update(computed)
        project = self.project(keep, keep=True)
        return project

    def _getLastStageKind(self, kind):
        # see if there is already an open projection stage
        for stage in self.stages[::-1]:
            if kind in stage:
                return stage

    def _getProjection(self, append=False):
        stage = self._getLastStageKind('$project')
        if stage is None or append:
            stage = {
                '$project': {
                    '_id': 1,
                }
            }
            self.stages.append(stage)
        return stage

    def _getGroupBy(self, by=None, append=False):
        stage = self._getLastStageKind('$group')
        if stage and stage['$group']['_id'] != by and by != '$$last':
            # if a different groupby criteria, add a new one
            stage = None
        if stage is None and by == '$$last':
            by = None
        if stage is None or append:
            stage = {
                '$group': {
                    '_id': by,
                }
            }
            self.stages.append(stage)
        return stage

    def groupby(self, by, expr=None, append=None, **kwargs):
        """
        add a groupby accumulation using $group

        :param by: the groupby columns, if provided as a list will be transformed
        :param expr:
        :param append:
        :param kwargs:
        :return:

        """
        by = make_tuple(by)
        self.index_columns = self.index_columns + list(by)
        # define groupby
        by = {col: '$' + col for col in by}
        stage = self._getGroupBy(by)
        groupby = stage['$group']
        # add acccumulators
        expr = expr or {
            col: colExpr
            for col, colExpr in six.iteritems(kwargs)}
        groupby.update(expr)
        # add a projection to extract groupby values
        extractId = {
            col: '$_id.' + col
            for col in by}
        # add a projection to keep accumulator columns
        keepCols = {
            col: 1
            for col in expr}
        keepCols.update(extractId)
        self.project(keepCols, append=True)
        # sort by groupby keys
        self.add({
            '$sort': {
                col: 1
                for col in by}
        })
        return self

    def project(self, expr=None, append=False, keep=False, **kwargs):
        """
        add a projection using $project

        :param expr: the column-operator mapping
        :param append: if True add a $project stage, otherwise add to existing
        :param kwargs: if expr is None, the column-operator mapping as kwargs
        :return: ApplyContext

        """
        # get last $project stage in pipeline
        stage = self._getProjection(append=append)
        expr = expr or kwargs
        self.expressions.append(expr)
        for k, v in six.iteritems(expr):
            # only append to stage if no other column projection was there
            project = stage.get('$project')
            if k not in project:
                project.update({
                    k: v
                })
            elif not keep:
                # if a column is already projected, add a new projection stage
                stage = self._getProjection(append=True)
                project = stage.get('$project')
                project.update({
                    k: v
                })
        return self


class ApplyArithmetics(object):
    """
    Math operators for ApplyContext

    * :code:`__mul__` (*)
    * :code:`__add__` (+)
    * :code:`__sub__` (-)
    * :code:`__div__` (/)
    * :code:`__floordiv__` (//)
    * :code:`__mod__` (%)
    * :code:`__pow__` (pow)
    * :code:`__ceil__` (ceil)
    * :code:`__floor__` (floor)
    * :code:`__trunc__` (trunc)
    * :code:`__abs__` (abs)
    * :code:`sqrt` (math.sqrt)

    """

    def __arithmop__(op, wrap_op=None):
        """
        return a pipeline $project stage math operator as
           { col:
              { '$operator': [ values, ...] }
              ...
           }

        If wrap_op is specified, will wrap the $operator clause as
           { col:
              { '$wrap_op': { '$operator': [ values, ...] } }0
              ...
           }
        """

        def inner(self, other):
            terms = []
            for term in make_tuple(other):
                if isinstance(term, six.string_types):
                    term = '$' + term
                terms.append(term)
            def wrap(expr):
                if wrap_op is not None:
                    expr = {
                        wrap_op: expr
                    }
                return expr
            mapping = {
                col: wrap({
                    op: ['$' + col] + terms,
                }) for col in self.columns}
            keepCols = {
                col: '$' + col
                for col in self.index_columns}
            mapping.update(keepCols)
            self.project(mapping)
            return self

        return inner

    #: multiply
    __mul__ = __arithmop__('$multiply')
    #: add
    __add__ = __arithmop__('$add')
    #: subtract
    __sub__ = __arithmop__('$subtract')
    #: divide
    __div__ = __arithmop__('$divide')
    __truediv__ = __arithmop__('$divide')
    #: divide integer
    __floordiv__ = __arithmop__('$divide', wrap_op='$floor')
    #: modulo (%)
    __mod__ = __arithmop__('$mod')
    #: pow
    __pow_ = __arithmop__('$pow')
    #: ceil
    __ceil__ = __arithmop__('$ceil')
    #: floor
    __floor__ = __arithmop__('$floor')
    #: truncate
    __trunc__ = __arithmop__('$trunc')
    #: absolute
    __abs__ = __arithmop__('$abs')
    #: square root
    sqrt = __arithmop__('sqrt')


class ApplyDateTime(object):
    """
    Datetime operators for ApplyContext
    """

    @property
    def dt(self):
        return self

    def __dtop__(op):
        """
        return a datetime $project operator as
           { col:
              { '$operator': '$col} }
              ...
           }
        """

        def inner(self, columns=None):
            columns = make_tuple(columns or self.columns)
            mapping = {
                col: {
                    op: '$' + col,
                }
                for col in columns}
            self.project(mapping)
            return self

        inner.__doc__ = op.replace('$', '')
        return inner

    # mongodb mappings
    _year = __dtop__('$year')
    _month = __dtop__('$month')
    _week = __dtop__('$week')
    _dayOfWeek = __dtop__('$dayOfWeek')
    _dayOfMonth = __dtop__('$dayOfMonth')
    _dayOfYear = __dtop__('$dayOfYear')
    _hour = __dtop__('$hour')
    _minute = __dtop__('$minute')
    _second = __dtop__('$second')
    _millisecond = __dtop__('$millisecond')
    _isoDayOfWeek = __dtop__('$isoDayOfWeek')
    _isoWeek = __dtop__('$isoWeek')
    _isoWeekYear = __dtop__('$isoWeekYear')

    # .dt accessor convenience similar to pandas.dt
    # see https://pandas.pydata.org/pandas-docs/stable/api.html#datetimelike-properties
    year = property(_year)
    month = property(_month)
    day = property(_dayOfMonth)
    hour = property(_hour)
    minute = property(_minute)
    second = property(_second)
    millisecond = property(_millisecond)
    week = property(_isoWeek)
    dayofyear = property(_dayOfYear)
    dayofweek = property(_dayOfWeek)


class ApplyString(object):
    """
    String operators
    """

    @property
    def str(self):
        return self

    def __strexpr__(op, unwind=False, base=None, max_terms=None):
        """
        return a pipeline $project string operator as
           { col:
              { '$operator': [ values, ...] }
              ...
           }
        """

        def inner(self, other, *args):
            # get all values passed and build terms from them
            values = list(make_tuple(other) + args)
            terms = []
            for term in values:
                if isinstance(term, six.string_types):
                    # if the term is a column name, add as a column name
                    if term in self.columns:
                        term = '$' + term
                    # allow to specify values explicitely by $$<value> => <value>
                    term = term.replace('$$', '')
                terms.append(term)
            # limit number of terms if requested
            if max_terms:
                terms = terms[:max_terms]
            # add projection of output columns to operator
            mapping = {
                col: {
                    op: terms if base is None else ['$' + col] + terms,
                } for col in self.columns}
            self.project(mapping)
            # unwind all columns if requested
            if unwind:
                exprs = [{'$unwind': {
                    'path': '$' + col
                }} for col in self.columns]
                self.stages.extend(exprs)
            return self

        inner.__doc__ = op.replace('$', '')
        return inner

    def __strunary__(op, unwind=False):
        """
        return a datetime $project operator as
           { col:
              { '$operator': '$col} }
              ...
           }
        """

        def inner(self, columns=None):
            columns = make_tuple(columns or self.columns)
            mapping = {
                col: {
                    op: '$' + col,
                }
                for col in columns}
            self.project(mapping)
            if unwind:
                self.stages.append({
                    '$unwind': {
                        ''
                    }
                })
            return self

            inner.__doc__ = op.replace('$', '')

        return inner

    def isequal(self, other):
        self.strcasecmp(other)
        # strcasecmp returns 0 for equality, 1 and -1 for greater/less than
        # https://docs.mongodb.com/manual/reference/operator/aggregation/strcasecmp/
        mapping = {
            col: {
                '$cond': {
                    'if': {'$eq': ['$' + col, 0]},
                    'then': True,
                    'else': False,
                }
            }
            for col in self.columns}
        self.project(mapping)

    concat = __strexpr__('$concat', base=True)
    split = __strexpr__('$split', unwind=True, base=True, max_terms=2)
    usplit = __strexpr__('$split', unwind=False, base=True, max_terms=2)
    upper = __strunary__('$toUpper')
    lower = __strunary__('$toLower')
    substr = __strexpr__('$substr', base=True)
    strcasecmp = __strexpr__('$strcasecmp', base=True)
    len = __strunary__('$strLenBytes')
    index = __strexpr__('$indexOfBytes', base=True)


class ApplyAccumulators(object):
    def agg(self, map=None, **kwargs):
        stage = self._getGroupBy(by='$$last')
        specs = map or kwargs
        for col, colExpr in six.iteritems(specs):
            if isinstance(colExpr, dict):
                # specify an arbitrary expression
                groupby = stage['$group']
                groupby[col] = colExpr
            elif isinstance(colExpr, six.string_types):
                # specify some known operator
                if hasattr(self, colExpr):
                    method = getattr(self, colExpr)
                    method(col)
                else:
                    raise SyntaxError('{} is not known'.format(colExpr))
            elif isinstance(colExpr, (tuple, list)):
                # specify a list of some known operators
                for statExpr in colExpr:
                    if hasattr(self, statExpr):
                        method = getattr(self, statExpr)
                        method(col)
                    else:
                        raise SyntaxError('{} is not known'.format(statExpr))
            elif callable(colExpr):
                # specify a callable that returns an expression
                groupby = stage['$group']
                groupby[col] = colExpr(col)
            else:
                SyntaxError('{} on column {} is unknown or invalid'.format(colExpr, col))
        return self

    def __statop__(op, opname=None):
        opname = opname or op.replace('$', '')

        def inner(self, columns=None):
            columns = make_tuple(columns or self.columns)
            stage = self._getGroupBy(by='$$last')
            groupby = stage['$group']
            groupby.update({
                               '{}_{}'.format(col, opname): {
                                   op: '$' + col
                               } for col in columns
                               })
            self.computed.extend(groupby.keys())
            self.project_keeper_columns()
            return self

        return inner

    sum = __statop__('$sum')
    avg = __statop__('$avg')
    mean = __statop__('$avg')
    min = __statop__('$min')
    max = __statop__('$max')
    std = __statop__('$stdDevSamp', 'std')


class ApplyCache(object):
    """
    A Cache that works on collections and pipelines
    """
    def __init__(self, db_alias):
        self._db_alias = db_alias

    def set(self, key, value):
        # https://stackoverflow.com/a/22003440/890242
        QueryCache = make_QueryCache(self._db_alias)
        QueryCache.objects(key=key).update_one(set__key="{}".format(key),
                                               set__value=value, upsert=True)

    def get(self, key):
        QueryCache = make_QueryCache(self._db_alias)
        try:
            result = QueryCache.objects.get(key=key)
        except:
            result = None
        return result


class ApplyStatistics(object):
    def quantile(self, q=.5):
        def preparefn(val):
            return val.pivot('percentile', 'var', 'value')
        return self.apply(self._percentile(q), preparefn=preparefn)

    def cov(self):
        def preparefn(val):
            val = val.pivot('x', 'y', 'cov')
            val.index.name = None
            val.columns.name = None
            return val
        return self.apply(self._covariance, preparefn=preparefn)

    def corr(self):
        def preparefn(val):
            val = val.pivot('x', 'y', 'rho')
            val.index.name = None
            val.columns.name = None
            return val
        return self.apply(self._pearson, preparefn=preparefn)

    def _covariance(self, ctx):
        # this works
        # source http://ci.columbia.edu/ci/premba_test/c0331/s7/s7_5.html
        facets = {}
        means = {}
        unwinds = []
        count = len(ctx.caller.noapply()) - 1
        for x, y in product(ctx.columns, ctx.columns):
            xcol = '$' + x
            ycol = '$' + y
            # only calculate the same column's mean once
            if xcol not in means:
                means[xcol] = ctx.caller[x].noapply().mean().values[0, 0]
            if ycol not in means:
                means[ycol] = ctx.caller[y].noapply().mean().values[0, 0]
            sumands = {
                xcol: {
                    '$subtract': [xcol, means[xcol]]
                },
                ycol: {
                    '$subtract': [ycol, means[ycol]]
                }
            }
            multiply = {
                '$multiply': [sumands[xcol], sumands[ycol]]
            }
            agg = {
                '$group': {
                    '_id': None,
                    'value': {
                        '$sum': multiply
                    }
                }
            }
            project = {
                '$project': {
                    'cov': {
                        '$divide': ['$value', count],
                    },
                    'x': x,
                    'y': y,
                }
            }
            pipeline = [agg, project]
            outcol = '{}_{}'.format(x, y)
            facets[outcol] = pipeline
            unwinds.append({'$unwind': '$' + outcol})
        facet = {
            '$facet': facets,
        }
        expand = [{
            '$project': {
                'value': {
                    '$objectToArray': '$$CURRENT',
                }
            }
        }, {
            '$unwind': '$value'
        }, {
            '$replaceRoot': {
                'newRoot': '$value.v'
            }
        }]
        return [facet, *unwinds, *expand]

    def _pearson(self, ctx):
        # this works
        # source http://ilearnasigoalong.blogspot.ch/2017/10/calculating-correlation-inside-mongodb.html
        facets = {}
        unwinds = []
        for x, y in product(ctx.columns, ctx.columns):
            xcol = '$' + x
            ycol = '$' + y
            sumcolumns = {'$group': {'_id': None,
                                     'count': {'$sum': 1},
                                     'sumx': {'$sum': xcol},
                                     'sumy': {'$sum': ycol},
                                     'sumxsquared': {'$sum': {'$multiply': [xcol, xcol]}},
                                     'sumysquared': {'$sum': {'$multiply': [ycol, ycol]}},
                                     'sumxy': {'$sum': {'$multiply': [xcol, ycol]}}
                                     }}

            multiply_sumx_sumy = {'$multiply': ["$sumx", "$sumy"]}
            multiply_sumxy_count = {'$multiply': ["$sumxy", "$count"]}
            partone = {'$subtract': [multiply_sumxy_count, multiply_sumx_sumy]}

            multiply_sumxsquared_count = {'$multiply': ["$sumxsquared", "$count"]}
            sumx_squared = {'$multiply': ["$sumx", "$sumx"]}
            subparttwo = {'$subtract': [multiply_sumxsquared_count, sumx_squared]}

            multiply_sumysquared_count = {'$multiply': ["$sumysquared", "$count"]}
            sumy_squared = {'$multiply': ["$sumy", "$sumy"]}
            subpartthree = {'$subtract': [multiply_sumysquared_count, sumy_squared]}

            parttwo = {'$sqrt': {'$multiply': [subparttwo, subpartthree]}}

            rho = {'$project': {
                'rho': {
                    '$divide': [partone, parttwo]
                },
                'x': x,
                'y': y
            }}
            pipeline = [sumcolumns, rho]
            outcol = '{}_{}'.format(x, y)
            facets[outcol] = pipeline
            unwinds.append({'$unwind': '$' + outcol})
        facet = {
            '$facet': facets,
        }
        expand = [{
            '$project': {
                'value': {
                    '$objectToArray': '$$CURRENT',
                }
            }
        }, {
            '$unwind': '$value'
        }, {
            '$replaceRoot': {
                'newRoot': '$value.v'
            }
        }]
        return [facet, *unwinds, *expand]

    def _percentile(self, pctls=None):
        """
        calculate percentiles for all columns
        """
        pctls = pctls or [.25, .5, .75]
        if not isinstance(pctls, (list, tuple)):
                pctls = [pctls]

        def calc(col, p, outcol):
            # sort values
            sort = {
                '$sort': {
                    col: 1,
                }
            }
            # group/push to get an array of all values
            group = {
                '$group': {
                    '_id': col,
                    'values': {
                        '$push': "$" + col
                    },
                }
            }
            # find value at requested percentile
            perc = {
                '$arrayElemAt': [
                    '$values', {
                        '$floor': {
                        '$multiply': [{
                            '$size': '$values'
                        }, p]
                    }}
                ]
            }
            # map percentile value to output column
            project = {
                '$project': {
                    'var': col,
                    'percentile': 'p{}'.format(p),
                    'value': perc,
                }
            }
            return [sort, group, project]

        def inner(ctx):
            # for each column and requested percentile, build a pipeline
            # all pipelines will be combined into a $facet stage to
            # calculate every column/percentile tuple in parallel
            facets = {}
            unwind = []
            # for each column build a pipeline to calculate the percentiles
            for col in ctx.columns:
                for p in pctls:
                    # e.g. outcol for perc .25 of column abc => abcp25
                    outcol = '{}_p{}'.format(col, p).replace('0.', '')
                    facets[outcol] = calc(col, p, outcol)
                    unwind.append({'$unwind': '$'+ outcol})
            # process per-column pipelines in parallel, resulting in one
            # document for each variable + percentile combination
            facet = {
                '$facet': facets
            }
            # expand single document into one document per variable + percentile combo
            # the resulting set of documents contains var/percentile/value
            expand = [{
                '$project': {
                    'value': {
                        '$objectToArray': '$$CURRENT',
                    }
                }
            }, {
                '$unwind': '$value'
            }, {
                '$replaceRoot': {
                    'newRoot': '$value.v'
                }
            }]
            pipeline = [facet, *unwind, *expand]
            return pipeline

        return inner


