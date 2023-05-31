import os
from unittest import mock

import numpy as np
import pandas as pd
from django.contrib.auth.models import User
from django.test import TestCase
from numpy.testing import assert_almost_equal
from sklearn.linear_model import LinearRegression
from sklearn.linear_model import SGDRegressor, LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from tastypie.test import ResourceTestCaseMixin

from omegaml import Omega
from omegaml.sklext import OnlinePipeline
from omegaops import get_client_config
from omegaweb.tests.util import OmegaResourceTestMixin


# ensure the client uses the server-specified mongo url
@mock.patch.dict(os.environ, {"OMEGA_MONGO_URL": ""})
class ModelResourceTestsAsync(OmegaResourceTestMixin, ResourceTestCaseMixin, TestCase):
    fixtures = ['landingpage']

    def setUp(self):
        super(ModelResourceTestsAsync, self).setUp()
        # self.api_client = ClientRequestTracer(self.api_client)
        # setup django user
        self.username = username = 'test'
        self.email = email = 'test@omegaml.io'
        self.password = password = 'password'
        self.user = User.objects.create_user(username, email, password)
        self.apikey = self.user.api_key.key
        # setup omega credentials
        self.setup_initconfig()
        # setup test data
        config = get_client_config(self.user)
        om = self.om = Omega(mongo_url=config.get('OMEGA_MONGO_URL'))
        for ds in om.datasets.list():
            om.datasets.drop(ds)
        for ds in om.models.list():
            om.models.drop(ds)

    def tearDown(self):
        pass

    def url(self, pk=None, action=None, query=None):
        url = '/api/v1/model/'
        if pk is not None:
            url += '{pk}/'.format(**locals())
        if action is not None:
            url += '{action}/'.format(**locals())
        if query is not None:
            url += '?{query}'.format(**locals())
        return url

    @property
    def _async_header(self):
        return dict(HTTP_ASYNC=True)

    def get_credentials(self):
        return self.create_apikey(self.username, self.apikey)

    def test_predict_from_dataset(self):
        om = self.om
        x = np.array(list(range(1, 100)))
        y = x * 2
        df = pd.DataFrame({'x': x,
                           'y': y})
        X = df[['x']]
        Y = df[['y']]
        om.datasets.put(X, 'X', append=False)
        om.datasets.put(Y, 'Y', append=False)
        # create a pipeline, fit, store
        p = Pipeline([
            ('lr', LinearRegression()),
        ])
        p.fit(X, Y)
        # execute pipeline via API and get results
        om.models.put(p, 'mymodel')
        resp = self.api_client.put(self.url('mymodel', 'predict', 'datax=X'),
                                   authentication=self.get_credentials(),
                                   **self._async_header)
        resp = self._check_async(resp)
        self.assertEqual(resp.status_code, 200)
        data = self.deserialize(resp)['response']
        assert_almost_equal(data.get('result'), list(df['y'].astype(float)))

    def test_predict_from_data(self):
        om = self.om
        x = np.array(list(range(1, 100)))
        y = x * 2
        df = pd.DataFrame({'x': x,
                           'y': y})
        X = df[['x']]
        Y = df[['y']]
        om.datasets.put(X, 'X', append=False)
        om.datasets.put(Y, 'Y', append=False)
        # create a pipeline, fit, store
        p = Pipeline([
            ('lr', LinearRegression()),
        ])
        p.fit(X, Y)
        # execute pipeline via API and get results
        om.models.put(p, 'mymodel')
        data = {
            'columns': ['x'],
            'data': {'x': df['x'].values.tolist()},
            # 'shape': [1, len(df)],  # not needed here
        }
        resp = self.api_client.put(self.url('mymodel', 'predict'),
                                   data=data,
                                   authentication=self.get_credentials(),
                                   **self._async_header)
        resp = self._check_async(resp)
        self.assertEqual(resp.status_code, 200)
        data = self.deserialize(resp)['response']
        assert_almost_equal(data.get('result'), list(df['y'].astype(float)))

    def test_fit(self):
        om = self.om
        x = np.array(list(range(1, 100)))
        y = x * 2
        df = pd.DataFrame({'x': x,
                           'y': y})
        X = df[['x']]
        Y = df[['y']]
        om.datasets.put(X, 'X', append=False)
        om.datasets.put(Y, 'Y', append=False)
        # create a pipeline without fitting yet
        p = Pipeline([
            ('lr', LinearRegression()),
        ])
        om.models.put(p, 'mymodel')
        # try to predict without fitting
        resp = self.api_client.put(self.url('mymodel', 'predict', 'datax=X'),
                                   authentication=self.get_credentials(),
                                   **self._async_header)
        resp = self._check_async(resp)
        self.assertHttpBadRequest(resp)
        # fit remotely
        resp = self.api_client.put(self.url('mymodel', 'fit',
                                            'datax=X&datay=Y'),
                                   data={},
                                   authentication=self.get_credentials(),
                                   **self._async_header)
        resp = self._check_async(resp)
        self.assertHttpOK(resp)
        # predict
        resp = self.api_client.put(self.url('mymodel', 'predict', 'datax=X'),
                                   authentication=self.get_credentials(),
                                   **self._async_header)
        resp = self._check_async(resp)
        self.assertHttpOK(resp)
        data = self.deserialize(resp)['response']
        assert_almost_equal(data.get('result'), list(df['y'].astype(float)))

    def test_partial_fit(self):
        om = self.om
        x = np.array(list(range(1, 10000)))
        y = x * 2
        df = pd.DataFrame({'x': x,
                           'y': y})
        X = df[['x']]
        Y = df[['y']]
        om.datasets.put(X, 'X', append=False)
        om.datasets.put(Y, 'Y', append=False)
        # create a pipeline without fitting yet
        p = OnlinePipeline([
            ('scale', StandardScaler()),
            ('sgdr', SGDRegressor(random_state=42, learning_rate='optimal',
                                  penalty=None, max_iter=10, tol=1e-3)),
        ])
        om.models.put(p, 'mymodel')
        # try to predict without fitting
        resp = self.api_client.put(self.url('mymodel', 'predict', 'datax=X'),
                                   authentication=self.get_credentials(),
                                   **self._async_header)
        resp = self._check_async(resp)
        self.assertHttpBadRequest(resp)
        # fit remotely, note since we partial_fit we have to n_iter ourselves
        n_iter = 2
        for i in range(n_iter):
            resp = self.api_client.put(self.url('mymodel', 'partial_fit',
                                                'datax=X&datay=Y'),
                                       data={},
                                       authentication=self.get_credentials(),
                                       **self._async_header)
            resp = self._check_async(resp)
            self.assertHttpOK(resp)
        # predict
        resp = self.api_client.put(self.url('mymodel', 'predict', 'datax=X'),
                                   authentication=self.get_credentials(),
                                   **self._async_header)
        resp = self._check_async(resp)
        self.assertHttpOK(resp)
        data = self.deserialize(resp)['response']
        assert_almost_equal(data.get('result'), list(df['y'].astype(float)))

    def test_score(self):
        om = self.om
        x = np.array(list(range(1, 100)))
        y = x * 2
        df = pd.DataFrame({'x': x,
                           'y': y})
        X = df[['x']]
        Y = df[['y']]
        om.datasets.put(X, 'X', append=False)
        om.datasets.put(Y, 'Y', append=False)
        # create a pipeline without fitting yet
        p = Pipeline([
            ('lr', LinearRegression()),
        ])
        om.models.put(p, 'mymodel')
        # try to predict without fitting
        resp = self.api_client.put(self.url('mymodel', 'predict', 'datax=X'),
                                   authentication=self.get_credentials(),
                                   **self._async_header)
        resp = self._check_async(resp)
        self.assertHttpBadRequest(resp)
        # fit remotely
        resp = self.api_client.put(self.url('mymodel', 'fit',
                                            'datax=X&datay=Y'),
                                   data={},
                                   authentication=self.get_credentials(),
                                   **self._async_header)
        resp = self._check_async(resp)
        self.assertHttpOK(resp)
        # score
        resp = self.api_client.get(self.url('mymodel', 'score',
                                            'datax=X&datay=Y'),
                                   authentication=self.get_credentials(),
                                   **self._async_header)
        resp = self._check_async(resp)
        self.assertHttpOK(resp)
        data = self.deserialize(resp)['response']
        # fit locally for comparison
        p.fit(X, Y)
        score = p.score(X, Y)
        assert_almost_equal(data.get('result'), score)

    def test_transform(self):
        om = self.om
        x = np.array(list(range(1, 100)))
        y = x * 2
        df = pd.DataFrame({'x': x,
                           'y': y})
        X = df[['x']]
        Y = df[['y']]
        om.datasets.put(X, 'X', append=False)
        om.datasets.put(Y, 'Y', append=False)
        # create a pipeline without fitting yet
        p = Pipeline([
            ('lr', StandardScaler()),
        ])
        om.models.put(p, 'mymodel')
        # try to predict without fitting
        resp = self.api_client.get(self.url('mymodel', 'transform', 'datax=X'),
                                   authentication=self.get_credentials(),
                                   **self._async_header)
        resp = self._check_async(resp)
        self.assertHttpBadRequest(resp)
        # fit remotely
        resp = self.api_client.put(self.url('mymodel', 'fit',
                                            'datax=X&datay=Y'),
                                   data={},
                                   authentication=self.get_credentials(),
                                   **self._async_header)
        resp = self._check_async(resp)
        self.assertHttpOK(resp)
        # score
        resp = self.api_client.get(self.url('mymodel', 'transform',
                                            'datax=X'),
                                   authentication=self.get_credentials(),
                                   **self._async_header)
        resp = self._check_async(resp)
        self.assertHttpOK(resp)
        data = self.deserialize(resp)['response']
        # do the same locally
        p.fit(X, Y)
        transformed = p.transform(X).flatten().tolist()
        assert_almost_equal(data.get('result'), transformed)

    def test_decision_function(self):
        om = self.om
        x = np.array(list(range(1, 100)))
        y = x * 2
        df = pd.DataFrame({'x': x,
                           'y': y})
        X = df[['x']]
        Y = df[['y']]
        om.datasets.put(X, 'X', append=False)
        om.datasets.put(Y, 'Y', append=False)
        # create a pipeline without fitting yet
        p = Pipeline([
            ('lr', LogisticRegression()),
        ])
        om.models.put(p, 'mymodel')
        # try to predict without fitting
        resp = self.api_client.get(self.url('mymodel', 'decision_function', 'datax=X'),
                                   authentication=self.get_credentials(),
                                   **self._async_header)
        resp = self._check_async(resp)
        self.assertHttpBadRequest(resp)
        # fit remotely
        resp = self.api_client.put(self.url('mymodel', 'fit',
                                            'datax=X&datay=Y'),
                                   data={},
                                   authentication=self.get_credentials(),
                                   **self._async_header)
        resp = self._check_async(resp)
        self.assertHttpOK(resp)
        # score
        resp = self.api_client.get(self.url('mymodel', 'decision_function',
                                            'datax=X'),
                                   authentication=self.get_credentials(),
                                   **self._async_header)
        resp = self._check_async(resp)
        self.assertHttpOK(resp)
        data = self.deserialize(resp)['response']
        # do the same locally
        p.fit(X, Y)
        transformed = p.decision_function(X).flatten().tolist()
        assert_almost_equal(data.get('result'), list(transformed))


