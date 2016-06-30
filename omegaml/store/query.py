import copy

from omegaml.store.queryops import MongoQueryOps


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

    def __repr__(self):
        r = []
        for op, q in self.qlist:
            r.append('%s %s' % (op, q.conditions))
        return 'Q %s' % ('\n'.join(r))

    def value(self, collection):
        return self.apply_filter(collection)

    def apply_filter(self, collection):
        query = self.build_filters()
        return self.apply_conditions(collection, query)

    def apply_conditions(self, collection, query):
        return collection.find(query)

    def build_filters(self):
        query = {}
        for i, (op, q) in enumerate(self.qlist):
            if i == 0:
                query = q.build_conditions()
            elif op == '&':
                query.setdefault("$and", [])
                fn = q.build_conditions if q == self else q.build_filters
                query["$and"].append(fn())
            elif op == '|':
                fn = q.build_conditions if q == self else q.build_filters
                if i == 1:
                    query = {"$or": [dict(query)]}
                else:
                    query.setdefault("$or", [])
                query["$or"].append(fn())
        return query

    def build_conditions(self):
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
        for k, v in self.conditions.iteritems():
            if '__' in k:
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
            elif op == 'contains':
                addq(k, qops.REGEX('^%s.*' % v))
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
        if self._inv:
            _query = {}
            for k, v in query.iteritems():
                if not isinstance(v, (basestring, float, int, long)):
                    _query[k] = qops.NOT(v)
                else:
                    _query[k] = qops.NOT(qops.EQ(v))
            return _query
        return query

    def negate(self):
        self._inv = True
        return self

    def __and__(self, other):
        q = copy.deepcopy(self)
        q.qlist.append(('&', other))
        return q

    def __or__(self, other):
        q = copy.deepcopy(self)
        q.qlist.append(('|', other))
        return q

    def __invert__(self):
        """
        return an inverted version of this object
        """
        notq = MongoQ(**self.conditions).negate()
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
        self.coll = coll
        self.trace = False
        self.exc = None
        self.q = self.build_query(__query, **kwargs)

    def build_query(self, __query=None, **kwargs):
        if __query:
            q = __query
        else:
            q = MongoQ(**kwargs)
        return q

    @property
    def query(self):
        return self.q.build_filters()

    def count(self):
        return len(self.value.index)

    @property
    def value(self):
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
        self.q &= self.build_query(query, **kwargs)
        return self

    def exclude(self, query=None, **kwargs):
        self.q &= ~self.build_query(query, **kwargs)
        return self

    def evaluate(self):
        result = self.q.apply_filter(self.coll)
        try:
            import pandas as pd
            result = pd.DataFrame(list(result))
            if '_id' in result.columns:
                del result['_id']
        except ImportError:
            result = list(result)
        return result

    def _repr_html_(self):
        return self.value._repr_html_()

    def __repr__(self):
        return self.value.__repr__()
