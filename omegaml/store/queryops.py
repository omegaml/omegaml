import sys

import pymongo


class MongoQueryOps(object):
    UNARY = ('IN,LT,LTE,GT,GTE,NE,WHERE,GEOWITHIN,ALL,ELEMWITHIN,NIN'
             'EXISTS,TYPE,REGEX,EQ')
    """
    Simplified mongo query terms

    Examples:

    # setup
    x = MongoQueryOps()
    d = dict

    # build queries
    query = x.MATCH(d(foo='value', baz=x.CONTAINS('value'))) 
    groupby = x.GROUP(columns=[col1, col2]), count=x.COUNT())

    result = coll.find(query)
    result = coll.aggregate([query, groupby])
    """
    def __getattr__(self, k):
        if k.upper().replace('_', '') in MongoQueryOps.UNARY.split(','):
            return self.__unary(k.lower())
        raise AttributeError('operator %s is not supported' % k)
    def __unary(self, op):
        """
        return a function to create unary operators

        e.g. MongoQueryOps().lt(val) will return an unary function
        that on being called will return { "$lt" : val }
        """
        def unary(val):
            return {"$%s" % op.lower(): val}
        return unary
    def OR(self, sub):
        return {"$or": sub}
    def AND(self, sub):
        return {"$and": sub}
    def NOT(self, sub):
        return {"$not": sub}
    def GROUP(self, v=None, columns=None, **kwargs):
        from collections import OrderedDict
        if not v:
            v = OrderedDict()
        if columns:
            v.setdefault('_id', {})
            v['_id'].update({k: '$%s' % (k.replace('__', '.'))
                             for k in columns})
        if kwargs:
            for _k, _v in kwargs.iteritems():
                v.setdefault(_k, {})
                if isinstance(_v, dict):
                    v[_k].update(_v)
                else:
                    v[_k] = _v
        return {"$group": v}
    def SUM(self, v):
        return {"$sum": v}
    def COUNT(self):
        return self.SUM(1)
    def as_dataframe(self, result, autoflat=True, flatten=None, groupby=None):
        """ transform a resultset into a dataframe"""
        import pandas as pd
        def do_flatten(seq):
            """ extract composed keys into columns """
            for r in seq:
                row = {}
                row.update(r)
                if flatten in row.keys():
                    row.update(row.get(flatten))
                yield row
        if autoflat or flatten == True:
            flatten = '_id'
        df = pd.DataFrame(do_flatten(result))
        if groupby and len(df.index) > 0:
            if isinstance(groupby, bool):
                cols = df.iloc[0]['_id'].keys()
            else:
                cols = groupby
            df.set_index(cols, inplace=True)
        return df
    def MATCH(self, *args, **kwargs):
        if args:
            v = args[0]
        else:
            v = kwargs
        return {"$match": v}
    def SEARCH(self, v):
        return {"$text": {"$search": v}}
    def CONTAINS(self, v):
        return {"$regex": '.*%s.*' % v}
    def SORT(self, **columns):
        return {"$sort": columns}
    def d(self, **kwargs):
        return dict(**kwargs)
    def to_latex(self, df, fout=None):
        fout = fout or sys.stdout
        fout.write(df.to_latex())
        return fout
    def LOOKUP(self, other, key=None, left_key=None, right_key=None,
               target=None):
        """
        return a $lookup statement.

        :param other: the other collection
        :param key: the key field (applies to both left and right)
        :param left_key: the left key field
        :param right_key: the right key field 
        :param target: the target array to store the matching other-documents
        """
        return {
            "$lookup": {
                "from": other,
                "localField": key or left_key,
                "foreignField": key or right_key,
                "as": target or ("%s_%s" % (other, key or right_key))
            }
        }
    def UNWIND(self, field):
        """
        returns $unwind for the given array field. the index in the
        array will be stored as _index_<field>. 
        """
        return {
            "$unwind": {
                "path": "$%s" % field,
                "includeArrayIndex": "%s_%s" % ('_index_', field),
                "preserveNullAndEmptyArrays": False
            }
        }
    def OUT(self, name):
        return {"$out": name}
    def make_index(self, columns, **kwargs):
        """
        using columns specs like ['+A', '-A'] returns (key, index)
        pairs suitable for passing on to create_index. also generates
        a name for the index based on the columns and ordering
        """
        sort_cols = ['+' + col if col[0] != '-' else col for col in columns]
        # get sort kwargs
        def direction(col):
            if col[0] == '-':
                d = pymongo.DESCENDING
            else:
                d = pymongo.ASCENDING
            return d
        idx = [(col.replace('+', '').replace('-', ''), direction(col))
               for col in sort_cols]
        name = '__'.join([col.replace('-', 'desc_').replace('+', 'asc_')
                          for col in sort_cols])
        kwargs.setdefault('name', name)
        return idx, kwargs
    def make_sortkey(self, columns, **kwargs):
        """
        using columns specs like ['+A', '-A'] returns (key, index)
        pairs suitable for passing on to collection.sort()
        """
        sort_key, _ = self.make_index(columns)
        return sort_key

# convenience accessors
x = MongoQueryOps()
d = dict
