from __future__ import absolute_import

import pandas as pd
import random
import warnings
from hashlib import sha256
from omegaml import Omega
from omegaml.store.filtered import FilteredCollection
from omegaml.util import signature
from unittest.case import TestCase


class FilteredCollectionTests(TestCase):

    def setUp(self):
        TestCase.setUp(self)
        df = pd.DataFrame({'x': list(range(0, 10)) + list(range(0, 10)),
                           'y': random.sample(list(range(0, 100)), 20)})
        om = Omega()
        om.datasets.put(df, 'sample', append=False)
        self.coll = om.datasets.collection('sample')

    def tearDown(self):
        TestCase.tearDown(self)

    def test_find(self):
        query = {'x': 1}
        fcoll = FilteredCollection(self.coll, query=query)
        result = list(fcoll.find())
        self.assertTrue(len(result) == 2)

    def test_find_one(self):
        query = {'x': 9}
        fcoll = FilteredCollection(self.coll, query=query)
        result = fcoll.find_one()
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get('x'), 9)

    def test_find_one_and_delete(self):
        query = {'x': 9}
        fcoll = FilteredCollection(self.coll, query=query)
        result = fcoll.find_one_and_delete()
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get('x'), 9)
        result = list(fcoll.find())
        self.assertEqual(len(result), 1)

    def test_find_one_and_replace(self):
        query = {'x': 9}
        fcoll = FilteredCollection(self.coll, query=query)
        result = fcoll.find_one_and_replace({'x': 9, 'xy': 9000})
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get('x'), 9)
        result_n = fcoll.find_one()
        self.assertEqual(result_n.get('xy'), 9000)
        self.assertNotIn('y', result_n)

    def test_find_one_and_update(self):
        query = {'x': 9}
        fcoll = FilteredCollection(self.coll, query=query)
        result = fcoll.find_one_and_update({'$set': {'xy': 9000}})
        # make sure we get what we wanted
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get('x'), 9)
        # be sure to get the same as before, then test it was updated
        result_n = fcoll.find_one({'_id': result.get('_id')})
        self.assertEqual(result_n.get('xy'), 9000)
        self.assertEqual(result_n.get('y'), result.get('y'))

    def test_count(self):
        query = {'x': 9}
        fcoll = FilteredCollection(self.coll, query=query)
        result = fcoll.count_documents()
        self.assertEqual(result, 2)

    def test_distinct(self):
        query = {'x': 9}
        fcoll = FilteredCollection(self.coll, query=query)
        result = fcoll.distinct('x')
        self.assertEqual(result, [9])

    def test_injection(self):
        # check that injected $where statements are not executed
        # -- if executed would return all rows (all row conditions true)
        # -- if properly sanitized will return zero rows because the
        #    the $where clause is replaced by -where, not matching any rows
        injected = {
            "$where": "function() { return true; }"
        }
        with warnings.catch_warnings(record=True) as wrn:
            warnings.simplefilter('always')
            fcoll = FilteredCollection(self.coll, query=injected)
            result = fcoll.count_documents()
            warnlog = str(list(w.message for w in wrn))
            self.assertIn('$where clauses are not permitted and replaced by -where for security reasons.', warnlog)
        self.assertEqual(result, 0)
        # check that nested $where statements are not executed
        # -- if executed would return all rows (all row conditions true)
        # -- if properly sanitized will return zero rows because the
        #    the $where clause is replaced by -where, not matching any rows
        injected = {
            "$or": [{
                "x": -1,
                "$where": "function() { return true; }"
            }]
        }
        fcoll = FilteredCollection(self.coll, query=injected)
        result = fcoll.count_documents()
        # if $where is executed we get rows back, else None (x == -1 is never true)
        self.assertEqual(result, 0)

    def test_trusted_filter(self):
        filter = {
            "x": {'$in': [1, 2]}
        }
        for trusted in [False, True, None, sha256(str(filter).encode('utf-8')).hexdigest()]:
            with warnings.catch_warnings(record=True) as wrn:
                warnings.simplefilter('always')
                fcoll = FilteredCollection(self.coll, query=filter, trusted=trusted)
                result = fcoll.count_documents()
                warnlog = str(list(w.message for w in wrn))
                self.assertIn('Your MongoDB query contains operators [\'$in\'] which may be unsafe if not sanitized.',
                              warnlog)
                self.assertEqual(result, 4)
        with warnings.catch_warnings(record=True) as wrn:
            warnings.simplefilter('always')
            fcoll = FilteredCollection(self.coll, query=filter, trusted=signature(filter))
            result = fcoll.count_documents()
            warnlog = str(list(w.message for w in wrn))
            self.assertNotIn('Your MongoDB query contains operators [\'$in\'] which may be unsafe if not sanitized.',
                             warnlog)
            self.assertEqual(result, 4)
