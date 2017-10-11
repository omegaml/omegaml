import os
import random

from tastypie.test import ResourceTestCase

from omegaml import Omega
import pandas as pd
from pandas.util.testing import assert_frame_equal


class DatasetResourceTests(ResourceTestCase):

    def setUp(self):
        super(DatasetResourceTests, self).setUp()
        df = self.df = pd.DataFrame({'x': list(range(0, 10)) + list(range(0, 10)),
                                     'y': random.sample(list(range(0, 100)), 20)})
        om = self.om = Omega()
        for ds in om.datasets.list():
            om.datasets.drop(ds)
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
        test dataset listing 
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

    def test_get_dataset(self):
        """
        test get a dataset 
        """
        # -- get orient=dict
        resp = self.api_client.get(self.url('sample'))
        self.assertHttpOK(resp)
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

    def test_get_dataset_filtered(self):
        """
        test get a dataset 
        """
        # -- try some filter
        resp = self.api_client.get(self.url('sample', 'x__gt=5'))
        df = self.restore_dataframe(self.deserialize(resp))
        sdf = self.df[self.df.x > 5]
        assert_frame_equal(df, sdf, check_index_type=False)
        # -- try some more
        resp = self.api_client.get(self.url('sample', 'x=5'))
        df = self.restore_dataframe(self.deserialize(resp))
        sdf = self.df[self.df.x == 5]
        assert_frame_equal(df, sdf, check_index_type=False)
        # -- try some more
        resp = self.api_client.get(self.url('sample', 'x=5&y__gt=2'))
        df = self.restore_dataframe(self.deserialize(resp))
        sdf = self.df[(self.df.x == 5) & (self.df.y > 2)]
        assert_frame_equal(df, sdf, check_index_type=False)

    def test_create_dataset(self):
        data = {
            'append': False,
            'data': self.df.to_dict('records'),
            'orient': 'columns',
            'index': {
                'type': type(self.df.index).__name__,
                'values': list(self.df.index.values),

            }
        }
        # put twice to see if it really creates, not appends
        resp = self.api_client.put(self.url('newdata'), data=data)
        resp = self.api_client.put(self.url('newdata'), data=data)
        df = self.om.datasets.get('newdata')
        assert_frame_equal(df, self.df)

    def test_append_dataset(self):
        data = {
            'append': True,
            'data': self.df.to_dict('records'),
            'orient': 'columns',
            'index': {
                'type': type(self.df.index).__name__,
                'values': list(self.df.index.values),

            }
        }
        # put twice to see if it really appends, not replaces
        resp = self.api_client.put(self.url('newdata'), data=data)
        resp = self.api_client.put(self.url('newdata'), data=data)
        df = self.om.datasets.get('newdata')
        assert_frame_equal(df, self.df.append(self.df))

    def test_drop_dataset(self):
        # see if a dataset does not exist
        resp = self.api_client.delete(self.url('newdata'))
        self.assertEqual(resp.status_code, 404)
        # put a dataset and delete it
        data = {
            'append': True,
            'data': self.df.to_dict('records'),
            'orient': 'columns',
            'index': {
                'type': type(self.df.index).__name__,
                'values': list(self.df.index.values),

            }
        }
        resp = self.api_client.put(self.url('newdata'), data=data)
        self.assertEqual(resp.status_code, 204)
        resp = self.api_client.delete(self.url('newdata'))
        self.assertEqual(resp.status_code, 204)
