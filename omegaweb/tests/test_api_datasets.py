import os
import random

import pandas as pd
from django.contrib.auth.models import User
from pandas.testing import assert_frame_equal
from six import iteritems
from tastypie.test import ResourceTestCaseMixin

from landingpage.models import ServicePlan
from omegaops import get_client_config
from omegaweb.tests.util import OmegaResourceTestMixin


class DatasetResourceTests(OmegaResourceTestMixin, ResourceTestCaseMixin):
    def setUp(self):
        from omegaml import Omega

        super(DatasetResourceTests, self).setUp()
        # setup django user
        self.username = username = 'test'
        self.email = email = 'test@omegaml.io'
        self.password = password = 'password'
        self.user = User.objects.create_user(username, email, password)
        self.apikey = self.user.api_key.key
        # setup omega credentials
        self.setup_initconfig()
        # setup test data
        df = self.df = pd.DataFrame({'x': list(range(0, 10)) + list(range(0, 10)),
                                     'y': random.sample(list(range(5, 100)), 20)})
        config = get_client_config(self.user)
        om = self.om = Omega(mongo_url=config.get('OMEGA_MONGO_URL'))
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

    def get_credentials(self):
        return self.create_apikey(self.username, self.apikey)

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
        resp = self.api_client.get(self.url(),
                                   authentication=self.get_credentials())
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
        resp = self.api_client.get(
            self.url('sample'), authentication=self.get_credentials())
        self.assertHttpOK(resp)
        df = self.restore_dataframe(self.deserialize(resp))
        assert_frame_equal(df, self.df, check_index_type=False)
        # -- get orient=records
        resp = self.api_client.get(self.url('sample', 'orient=records'),
                                   authentication=self.get_credentials())
        df = self.restore_dataframe(self.deserialize(resp), 'records')
        assert_frame_equal(df, self.df, check_index_type=False)
        # -- get orient=list
        resp = self.api_client.get(self.url('sample', 'orient=list'),
                                   authentication=self.get_credentials())
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
        resp = self.api_client.get(self.url('sample', 'x__gt=5'),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        df = self.restore_dataframe(self.deserialize(resp))
        sdf = self.df[self.df.x > 5]
        assert_frame_equal(df, sdf, check_index_type=False)
        # -- try some more
        resp = self.api_client.get(self.url('sample', 'x=5'),
                                   authentication=self.get_credentials())
        df = self.restore_dataframe(self.deserialize(resp))
        sdf = self.df[self.df.x == 5]
        assert_frame_equal(df, sdf, check_index_type=False)
        # -- try some more
        resp = self.api_client.get(self.url('sample', 'x=5&y__gt=2'),
                                   authentication=self.get_credentials())
        df = self.restore_dataframe(self.deserialize(resp))
        sdf = self.df[(self.df.x == 5) & (self.df.y > 2)]
        assert_frame_equal(df, sdf, check_index_type=False)

    def test_create_dataset(self):
        data = pandas_to_apidata(self.df, append=False)
        # put twice to see if it really creates, not appends
        resp = self.api_client.put(self.url('newdata'), data=data,
                                   authentication=self.get_credentials())
        resp = self.api_client.put(self.url('newdata'), data=data,
                                   authentication=self.get_credentials())
        df = self.om.datasets.get('newdata')
        assert_frame_equal(df, self.df)

    def test_append_dataset(self):
        data = pandas_to_apidata(self.df, append=True)
        # put twice to see if it really appends, not replaces
        resp = self.api_client.put(self.url('newdata'), data=data,
                                   authentication=self.get_credentials())
        resp = self.api_client.put(self.url('newdata'), data=data,
                                   authentication=self.get_credentials())
        df = self.om.datasets.get('newdata')
        assert_frame_equal(df, self.df.append(self.df))

    def test_drop_dataset(self):
        # see if a dataset does not exist
        resp = self.api_client.delete(self.url('newdata'),
                                      authentication=self.get_credentials())
        self.assertEqual(resp.status_code, 404)
        # put a dataset and delete it
        data = pandas_to_apidata(self.df, append=True)
        resp = self.api_client.put(self.url('newdata'), data=data,
                                   authentication=self.get_credentials())
        self.assertEqual(resp.status_code, 204)
        resp = self.api_client.delete(self.url('newdata'),
                                      authentication=self.get_credentials())
        self.assertEqual(resp.status_code, 204)


def pandas_to_apidata(df, append=False):
    # TODO put logic for this into client lib
    data = {
        'append': append,
        'data': df.to_dict('records'),
        'dtypes': {k: str(v)
                   for k, v in iteritems(df.dtypes.to_dict())},
        'orient': 'columns',
        'index': {
            'type': type(df.index).__name__,
            # ensure type conversion to object for Py3 tastypie does
            # not recognize numpy.int64
            'values': list(df.index.astype('O').values),
        }
    }
    return data
