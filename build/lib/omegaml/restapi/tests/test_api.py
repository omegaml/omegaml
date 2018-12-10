from unittest import TestCase

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from omegaml import Omega
from omegaml.restapi.app import app


class OmegaRestApiTests(TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.om = Omega()

    def test_predict(self):
        X = np.arange(10).reshape(-1, 1)
        y = X * 2
        # train model locally
        clf = LinearRegression()
        clf.fit(X, y)
        result = clf.predict(X)
        # store model in om
        self.om.models.put(clf, 'regression')
        # check we can use it to predict
        resp = self.client.put('/v1/model/regression/predict', json={
            'columns': ['v'],
            'data': [dict(v=5)]
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get('model'), 'regression')
        self.assertEqual(data.get('result'), [[10.]])

    def test_dataset_query(self):
        om = self.om
        df = pd.DataFrame({
            'x': np.arange(100),
            'y': np.arange(100),
        })
        om.datasets.put(df, 'test', append=False)
        resp = self.client.get('/v1/dataset/test')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('data', data)
        self.assertIn('index', data)
        self.assertIn('values', data['index'])
        self.assertEqual(len(data['index']['values']), 100)
        self.assertEqual(len(data['data']['x']), 100)
        self.assertEqual(len(data['data']['y']), 100)

    def test_dataset_query_filter(self):
        om = self.om
        df = pd.DataFrame({
            'x': np.arange(100),
            'y': np.arange(100),
        })
        om.datasets.put(df, 'test', append=False)
        query = {
            'x__gte': 90,
        }
        resp = self.client.get('/v1/dataset/test', query_string=query)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('data', data)
        self.assertIn('index', data)
        self.assertIn('values', data['index'])
        self.assertEqual(len(data['index']['values']), 10)
        self.assertEqual(len(data['data']['x']), 10)
        self.assertEqual(len(data['data']['y']), 10)

    def test_dataset_put(self):
        om = self.om
        om.datasets.drop('foo', force=True)
        # create a new dataset
        data = {
            'data': {
                'x': list(range(10)),
                'y': list(range(10)),
                's': [str(v) for v in range(10)],
            },
            'dtypes': {
                's': 'str',
            },
            'append': False,
        }
        resp = self.client.put('/v1/dataset/foo', json=data)
        self.assertEqual(resp.status_code, 200)
        # -- see if we can query
        df = om.datasets.get('foo')
        self.assertEqual(10, len(df))
        self.assertEqual(list(range(10)), list(df['x']))
        self.assertEqual(list(range(10)), list(df['y']))
        self.assertEqual([str(v) for v in range(10)], list(df['s']))
        # append more records
        data['append'] = True
        resp = self.client.put('/v1/dataset/foo', json=data)
        self.assertEqual(resp.status_code, 200)
        df = om.datasets.get('foo')
        self.assertEqual(20, len(df))
        self.assertEqual(list(range(10)) * 2, list(df['x']))
        self.assertEqual(list(range(10)) * 2, list(df['y']))
        self.assertEqual([str(v) for v in list(range(10)) * 2], list(df['s']))


    def test_dataset_delete(self):
        om = self.om
        # test non-existent dataset
        om.datasets.drop('foo', force=True)
        resp = self.client.delete('/v1/dataset/foo')
        self.assertEqual(404, resp.status_code)
        df = pd.DataFrame({
            'x': np.arange(100),
            'y': np.arange(100),
        })
        # test existing dataset
        om.datasets.put(df, 'foo', append=False)
        resp = self.client.delete('/v1/dataset/foo')
        self.assertEqual(200, resp.status_code)
        self.assertEqual(None, om.datasets.get('foo'))
