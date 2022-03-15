from __future__ import absolute_import
import random
from unittest.case import TestCase

from pymongo.collection import Collection

from omegaml import Omega
from omegaml.store.filtered import FilteredCollection
import pandas as pd


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

