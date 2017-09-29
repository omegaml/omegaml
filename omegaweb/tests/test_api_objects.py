import random
from tastypie.test import ResourceTestCase

from omegaml import Omega
import pandas as pd


class ObjectResourceTests(ResourceTestCase):

    def setUp(self):
        super(ObjectResourceTests, self).setUp()
        df = self.df = pd.DataFrame({'x': list(range(0, 10)) + list(range(0, 10)),
                                     'y': random.sample(list(range(0, 100)), 20)})
        om = self.om = Omega()
        om.datasets.put(df, 'sample', append=False)
        self.coll = om.datasets.collection('sample')

    def testGetData(self):
        resp = self.api_client.get('/api/v1/object/')
        print(resp)
