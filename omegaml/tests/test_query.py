from __future__ import absolute_import
import random
from unittest.case import TestCase

from omegaml import Omega
from omegaml.mdataframe import MDataFrame
from omegaml.store import qops
from omegaml.store.query import Filter
from omegaml.store.queryops import GeoJSON
import pandas as pd
from six.moves import range
from pandas.util.testing import assert_frame_equal
# see https://gist.github.com/miraculixx/f01304186fc47d041da5a712774ac487
locations = [{'location': {'coordinates': [-74.0059413, 40.7127837],
                           'type': 'Point'},
              'place': 'New York'},
             {'location': {'coordinates': [6.1431577, 46.2043907],
                           'type': 'Point'},
              'place': 'Geneva'},
             {'location': {'coordinates': [7.4474468, 46.9479739],
                           'type': 'Point'},
              'place': 'Bern'},
             {'location': {'coordinates': [8.541694, 47.3768866],
                           'type': 'Point'},
              'place': 'Zurich'}]


class FilterQueryTests(TestCase):

    def setUp(self):
        TestCase.setUp(self)
        df = self.df = pd.DataFrame({'x': list(range(0, 10)) + list(range(0, 10)),
                                     'y': random.sample(list(range(0, 100)), 20)})
        om = self.om = Omega()
        om.datasets.put(df, 'sample', append=False)
        self.coll = om.datasets.collection('sample')

    def tearDown(self):
        TestCase.tearDown(self)

    def test_filter(self):
        coll = self.coll
        df = self.df
        result = Filter(coll, x=0).value
        testdf = df[df.x == 0]
        self.assertTrue(result.equals(testdf))

    def test_filter_in(self):
        coll = self.coll
        df = self.df
        result = Filter(coll, x__in=[1, 2, 3]).value
        testdf = df[df.x.isin([1, 2, 3])]
        self.assertTrue(result.equals(testdf))

    def test_filter_and(self):
        coll = self.coll
        df = self.df
        y = int(df.y.unique()[0])
        result = Filter(coll, x=0, y=y).value
        testdf = df[(df.x == 0) & (df.y == y)]
        self.assertTrue(result.equals(testdf))

    def test_filter_or(self):
        coll = self.coll
        df = self.df
        result = Filter(coll, x=0, y__gt=5).value
        testdf = df[(df.x == 0) & (df.y > 5)]
        self.assertTrue(result.equals(testdf))

    def test_filter_near(self):
        om = self.om
        # create a dataframe with geo locations
        geodf = pd.DataFrame(locations)
        geodf['location'] = geodf.location.apply(lambda v: GeoJSON(v))
        om.datasets.put(geodf, 'geosample', append=False, index='@location')
        coll = om.datasets.collection('geosample')
        # closest place
        result = Filter(coll,
                        location__near=dict(location=(8.541694, 47.3768866), maxd=1))
        places = result.value.place.unique()
        self.assertEqual(places, ['Zurich'])
        # ordered by distance
        result = Filter(coll,
                        location__near=dict(location=(8.541694, 47.3768866)))
        places = list(result.value.place.unique())
        self.assertListEqual(places, 'Zurich,Bern,Geneva,New York'.split(','))
        # use tuple (lon, lat, maxd)
        result = Filter(coll,
                        location__near=(8.541694, 47.3768866, 1))
        places = list(result.value.place.unique())
        self.assertListEqual(places, 'Zurich'.split(','))
        # use tuple (lon, lat, mind, maxd)
        result = Filter(coll,
                        location__near=(8.541694, 47.3768866, 0, 100))
        places = list(result.value.place.unique())
        self.assertListEqual(places, 'Zurich'.split(','))

    def test_filter_subdoc(self):
        coll = self.coll
        coll.update_many(qops.IS(x=qops.LT(5)), qops.SET('subdoc.a', 99))
        coll.update_many(qops.IS(x=qops.GTE(5)), qops.SET('subdoc.a', 0))
        result = Filter(coll, subdoc__a__lt=10).value
        self.assertEqual(set(result.x.unique()), set(range(5, 10)))

    def test_query_null(self):
        om = self.om
        df = pd.DataFrame({'x': list(range(0, 5)),
                           'y': [1, 2, 3, None, None]})
        om.datasets.put(df, 'foox', append=False)
        result = om.datasets.get('foox', y__isnull=True)
        test = df[df.isnull().any(axis=1)]
        assert_frame_equal(result, test)
