import os
import random

from tastypie.test import ResourceTestCase

from omegaml import Omega
from omegaweb.tests.util import assertDictEqualJSON
import pandas as pd
from pandas.util.testing import assert_frame_equal


class ObjectResourceTests(ResourceTestCase):

    def setUp(self):
        super(ObjectResourceTests, self).setUp()
        df = self.df = pd.DataFrame({'x': list(range(0, 10)) + list(range(0, 10)),
                                     'y': random.sample(list(range(0, 100)), 20)})
        om = self.om = Omega()
        om.datasets.put(df, 'sample', append=False)
        self.coll = om.datasets.collection('sample')

    def url(self, pk=None, query=None):
        url = '/api/v1/dataset/'
        if pk is not None:
            url += pk + '/'
        if query is not None:
            url += '?{query}'.format(**locals())
        return url

    def resource(self, filename):
        return os.path.join(os.path.dirname(__file__), 'resources', filename)

    def restore_dataframe(self, data, orient='dict'):
        if orient in ['dict', 'list']:
            df = pd.DataFrame.from_dict(data.get('data'))
            df.index = df.index.astype(int)
            df.sort_index(inplace=True)
            df.index = data['index']['values']
        elif orient == 'records':
            df = pd.DataFrame.from_records(data['data']['rows'])
            df.index = df.index.astype(int)
            df.sort_index(inplace=True)
            df.index = data['index']['values']
        return df

    def test_get_list(self):
        """
        test object listing 
        """
        om = self.om
        df = self.df
        om.datasets.put(df, 'sample2', append=False)
        resp = self.api_client.get(self.url())
        data = self.deserialize(resp)
        self.assertIn('meta', data)
        self.assertEqual(2, data.get('meta').get('total_count'))
        objects = [item.get('data').get('name')
                   for item in data.get('objects')]
        self.assertEqual(['sample', 'sample2'], objects)

    def test_get_object(self):
        """
        test get an object 
        """
        # -- get orient=dict
        resp = self.api_client.get(self.url('sample'))
        df = self.restore_dataframe(self.deserialize(resp))
        assert_frame_equal(df, self.df, check_index_type=False)
        # -- get orient=records
        resp = self.api_client.get(self.url('sample', 'orient=records'))
        df = self.restore_dataframe(self.deserialize(resp), 'records')
        assert_frame_equal(df, self.df, check_index_type=False)
        # -- get orient=list
        resp = self.api_client.get(self.url('sample', 'orient=list'))
        df = self.restore_dataframe(self.deserialize(resp), 'list')
        assert_frame_equal(df, self.df, check_index_type=False)

        # not currently supported
        # resp = self.api_client.get(self.url('sample', 'orient=series') #
        # resp = self.api_client.get(self.url('sample', 'orient=split'))
        # resp = self.api_client.get(self.url('sample', 'orient=index'))
