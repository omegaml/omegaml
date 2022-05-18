from unittest import TestCase

from omegaml.mixins.store.sqldb import DeferredCursor


class SQLDBTests(TestCase):
    def test_sqlize(self):
        cursor = DeferredCursor(None)
        # single row spec with value
        filter = {'a': 2}
        sqlfilter = cursor._sqlize(filter)
        self.assertEqual(sqlfilter, {'a': 2})
        # and-ed conditions
        filter = {'$and': [{'_om#rowid': {'$gte': 2}},
                           {'_om#rowid': {'$lte': 3}}]}
        sqlfilter = cursor._sqlize(filter)
        self.assertEqual(sqlfilter, {'_om#rowid__gte': 2, '_om#rowid__lte': 3})
        # single row spec with operator
        filter = {'a': {'$gte': 2}}
        sqlfilter = cursor._sqlize(filter)
        self.assertEqual(sqlfilter, {'a__gte': 2})
        # single row spec with operator
        filter = {'a': {'$gte': 2}}
        sqlfilter = cursor._sqlize(filter)
        self.assertEqual(sqlfilter, {'a__gte': 2})
        # single row spec with $in operator
        filter = {'a': {'$in': [2, 3]}}
        sqlfilter = cursor._sqlize(filter)
        self.assertEqual(sqlfilter, {'a__in': [2, 3]})
        # multiple row specs with operator
        filter = {'a': {'$gte': 2},
                  'b': {'$lte': 3}}
        sqlfilter = cursor._sqlize(filter)
        self.assertEqual(sqlfilter, {'a__gte': 2, 'b__lte': 3})

