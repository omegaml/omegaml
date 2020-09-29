import copy

import six

from omegaml.store.queryops import MongoQueryOps, flatten_keys
from omegaml.util import restore_index


class MongoQ(object):

    """
    Query object to filter mongodb collections

    A Q object holds the conditions. You can combine Q objects
    using & and | operators, e.g.

    q1 = Q(year=2015)
    q2 = Q(year=2014)
    q_all = q1 | q2

    Query objects are passed into a Filter, and evaluated when
    the filter's .value property is read.

    Conditions specified in one Q object are AND together. Various
    operators can be specified using __<op> syntax, e.g. year__eq=2015.

    eq     ==  (default)
    lt     <
    lte    <=
    gt     >
    gte    >=
    ne     <>
    not    <>
    in     isin(v)
    between

    startswith
    endwith
    contains
    match

    Evaluation works as follows:

    1. for each Q object, apply the filters as collection.find(query)
    2. return the dataframe

    """
    def __init__(self, **kwargs):
        self.conditions = kwargs
        self.qlist = [('', self)]
        # should we return ~(conditions)
        self._inv = False
        # is sorting implied by some operator
        self.sorted = False

    def __repr__(self):
        r = []
        for op, q in self.qlist:
            r.append('%s %s' % (op, q.conditions))
        return 'Q %s' % ('\n'.join(r))

    def value(self, collection):
        """
        resolve the query by actually applying the filter on given collection

        :param collection: the collection objec
        :return: the result of the apply_filter() call
        """
        return self.apply_filter(collection)

    def apply_filter(self, collection):
        """
        apply the filter to the given collection

        This builds the actual mongo query using build_filters and
        calls apply_conditions to execute the query

        :param collection: the collection object
        :return: the result of the apply_conditions() call
        """
        query = self.build_filters()
        return self.apply_conditions(collection, query)

    def apply_conditions(self, collection, query):
        """
        apply the mongo query on a given collection

        :param collection: the collection
        :param query: the query dictionary applicable to collection.find()
        :return: the result of collection.find()
        """
        operators = flatten_keys(query)
        if '$near' in operators:
            self.sorted = True
        return collection.find(query)

    def build_filters(self):
        """
        build the complex mongodb filter from query definitions

        This takes all query definitions in qlist, builds queries
        using .build_conditions() and concatenates the queries by
        and/or as defined the in qlist's op value.

        :return: the query suitable for the collection.find() method
        """
        query = {}
        for i, (op, q) in enumerate(self.qlist):
            if i == 0:
                query = q.build_conditions()
            elif op == '&':
                fn = q.build_conditions if q == self else q.build_filters
                if i == 1:
                    query = {"$and": [dict(query)]}
                else:
                    query.setdefault("$and", [])
                query["$and"].append(fn())
            elif op == '|':
                fn = q.build_conditions if q == self else q.build_filters
                if i == 1:
                    query = {"$or": [dict(query)]}
                else:
                    query.setdefault("$or", [])
                query["$or"].append(fn())
        if self._inv:
            query = {"$nor": [query]}
        return query

    def build_conditions(self):
        """
        For a given query definition return the collection.find() simple query

        Using all conditions, build the query as a dictionary suitable for
        collection.find(). This uses MongoQueryOps to transform query
        definitions into mongo db syntax.

        :return: the query in mongo db syntax
        """
        query = {}
        qops = MongoQueryOps()
        def addq(k, v):
            if k not in query:
                query[k] = v
            else:
                subq = []
                query.setdefault("$and", subq)
                for vv in [query.pop(k), v]:
                    if isinstance(vv, (list, tuple)):
                        subq.extend(vv)
                    else:
                        subq.append({k: vv})
        for k, v in six.iteritems(self.conditions):
            # transform query operators as '<foo>__<op>',
            # however preserve dunder '__<foo>' names ss columns
            if '__' in k and not k.startswith('__'):
                parts = k.split('__')
                k = '.'.join(parts[0:-1])
                op = parts[-1]
            else:
                op = 'eq'
            # standard logical operators
            if op == 'eq':
                addq(k, v)
            elif op.upper() in qops.UNARY:
                addq(k, getattr(qops, op)(v))
            # type queries
            elif op == 'between':
                addq("$and", [{k: qops.GTE(v[0])},
                              {k: qops.LTE(v[1])}])
            elif op == 'isstring':
                addq(k, qops.EQ(qops.TYPE('string')))
            elif op == 'isarray':
                addq(k, qops.EQ(qops.TYPE('array')))
            elif op == 'isdouble':
                addq(k, qops.TYPE('double'))
            elif op == 'isobject':
                addq(k, qops.TYPE('object'))
            elif op == 'isobject':
                addq(k, qops.TYPE('object'))
            elif op == 'isdate':
                addq(k, qops.TYPE('date'))
            elif op == 'isbool':
                addq(k, qops.TYPE('bool'))
            elif op == 'isnull':
                # http://stackoverflow.com/a/944733
                nan = float('nan')
                addq(k, qops.EQ(nan) if v else qops.NE(nan))
            elif op in ['islong', 'isint']:
                addq(k, qops.TYPE('long'))
            elif op == 'regex':
                addq(k, qops.REGEX(v))
            elif op == 'contains':
                addq(k, qops.REGEX('.*%s.*' % v))
            elif op == 'startswith':
                addq(k, qops.REGEX('^%s.*' % v))
            elif op == 'endswith':
                addq(k, qops.REGEX('.*%s$' % v))
            elif op == 'near':
                addq(k, qops.NEAR(v))
            else:
                # op from parts[-1] was not an opperator, so assume it is
                # an attribute name and apply the eq operator
                # e.g. Q(key__subkey=value)
                addq('%s.%s' % (k, op), v)
        return query

    def negate(self):
        """
        negate the query
        """
        self._inv = True
        return self

    def __and__(self, other):
        """
        combine with another MongoQ object using AND
        """
        q = copy.deepcopy(self)
        q.qlist.append(('&', other))
        return q

    def __or__(self, other):
        """
        combine with another MongoQ object using OR
        """
        q = copy.deepcopy(self)
        q.qlist.append(('|', other))
        return q

    def __invert__(self):
        """
        return an inverted version of this object
        """
        notq = copy.deepcopy(self).negate()
        return notq


class Filter(object):

    """
    Filter for OmegaStore objects

    Allow keyword style filtering of dataframes:

    direct filtering
        filter = Filter(df, year=2015)
        filter.value

    filtering with Q objects
        q = Q(year=2015)
        filter = Filter(df, q)

    filtering with multiple Q objects
        q1 = Q(year=2015)
        q2 = Q(year=2014)
        filter = Filter(df, q1 | q2)

    filtering with filter() and exclude()
        filter = Filter(df, year=2015)
        filter.filter(month=1)
        filter.exclude(day=15)
    """
    _debug = False

    def __init__(self, coll, __query=None, **kwargs):
        """
        Filter objects use MongoQ query expression to build
        complex filters.

        Internally, Filter keeps the .q MongoQ object to represent
        the filter. Filter thus is a thin wrapper around MongoQ to
        represent the human-readable high-level API to MongoQ:

        .filter -- add a new condition with AND
        .exclude -- exclude values given a condition
        .count -- count result lengths. note this triggers .value
        .value -- evaluate the filter

        In addition Filter supports tracing errors by using the .trace
        flag (set to True, defaults to False).

        :param coll: the collection to apply this filter to
        :param __query: a MongoQ object (used internally to combine
        filters)
        :param kwargs: the filter as a dict of column__op=value pairs
        """
        self.coll = coll
        self.trace = False
        self.exc = None
        self.q = self.build_query(__query, **kwargs)

    def build_query(self, __query=None, **kwargs):
        """
        build the MongoQ object from given kwargs

        Specify either the __query or the kwargs. If __query is
        specified it is returned unchanged. If kwargs is passed these
        are used to build a new MongoQ object. The rationale for this
        is so that build_query can be used without an if statement in
        the calling code (i.e. this methods wraps the if statement on
        whether to build a new MongoQ object or to use the existing,
        making for more readable code).

        :param __query: the MongoQ object to use
        :param kwargs: the filter as a dict of column__op=value pairs
        :return: the MongoQ object
        """
        if __query:
            q = __query
        else:
            q = MongoQ(**kwargs)
        return q

    @property
    def query(self):
        """
        Convenience method to return the filter's query in MongoDB syntax
        """
        return self.q.build_filters()

    def count(self):
        """
        Resolve the query and count number of rows
        """
        return len(self.value.index)

    @property
    def value(self):
        """
        Resolve the query and return its results

        Uses self.evaluate() in a safe manner.
        """
        try:
            value = self.evaluate()
        except KeyError as e:
            self.exc = e
            if self.trace:
                raise
            raise SyntaxError(
                'Error in Q object: column %s is unknown (KeyError on dataframe)' % e)
        return value

    def filter(self, query=None, **kwargs):
        """
        Add a new query expression using AND

        :param query: an existing MongoQ object (optional)
        :param kwargs: the kwargs as column__op=value pairs
        """
        self.q &= self.build_query(query, **kwargs)
        return self

    def exclude(self, query=None, **kwargs):
        """
        Add a new negated query expression

        This is the equivalent of .filter(~query)

        :param query: an existing MongoQ object (optional)
        :param kwargs: the kwargs as column__op=value pairs
        """
        self.q &= ~self.build_query(query, **kwargs)
        return self

    def __invert__(self):
        return Filter(self.coll, ~self.q)

    def __and__(self, other):
        return Filter(self.coll, self.q & other.q)

    def __or__(self, other):
        return Filter(self.coll, self.q | other.q)

    def evaluate(self):
        """
        evaluate the query

        :return: the pandas DataFrame
        """
        result = self.q.apply_filter(self.coll)
        try:
            import pandas as pd
            result = pd.DataFrame.from_records(result)
            if '_id' in result.columns:
                del result['_id']
            result = restore_index(result, dict(),
                                   rowid_sort=not self.q.sorted)
        except ImportError:
            result = list(result)
        return result

    def as_mask(self):
        """
        return the True mask of this filter

        note this does not actually return a mask but applies the filter
             to the real data. makes more sense even though the results
             are somewhat different this way, but match better semantically
        """
        return self.value == self.value

    def __repr__(self):
        return ' '.join(f'Filter({self.q})'.replace('\n', ' ').split())
