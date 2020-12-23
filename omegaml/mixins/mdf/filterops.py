from omegaml.mdataframe import MSeries
from omegaml.store import Filter
from omegaml.store import MongoQ


class FilterOpsMixin(object):
    """
    filter operators on MSeries
    """

    def __getfltop(op):
        def inner(self, other=True):
            return self.__fltop__(op, other)

        return inner

    def __fltop__(self, op, other):
        # the actual filter operator
        q = None
        for col in self.columns:
            queryop = '{col}__{op}'.format(col=col, op=op)
            value = other if not isinstance(other, MSeries) else '$' + other.columns[0]
            qq = MongoQ(**{queryop: value})
            if q is None:
                q = qq
            else:
                q = q | qq
        return Filter(self.collection, q)

    # see https://docs.mongodb.com/manual/reference/operator/query/
    __eq__ = __getfltop('eq')
    __ne__ = __getfltop('ne')
    __lt__ = __getfltop('lt')
    __le__ = __getfltop('lte')
    __gt__ = __getfltop('gt')
    __ge__ = __getfltop('gte')

    isnull = __getfltop('isnull')
