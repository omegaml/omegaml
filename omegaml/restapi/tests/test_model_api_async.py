from unittest import TestCase

import numpy as np
from numpy.testing import assert_almost_equal
from sklearn.linear_model import LinearRegression

from omegaml import Omega
from omegaml.client.auth import OmegaRestApiAuth
from omegaml.restapi.app import app
from omegaml.restapi.tests.util import RequestsLikeTestClient
from omegaml.tests.util import OmegaTestMixin


class OmegaRestAsyncApiTests(OmegaTestMixin, TestCase):
    def setUp(self):
        self.client = RequestsLikeTestClient(app)
        self.om = Omega()
        self.auth = OmegaRestApiAuth('user', 'pass')
        self.clean()

    @property
    def _headers(self):
        return {}

    def test_predict_from_data_inline(self):
        X = np.arange(10).reshape(-1, 1)
        y = X * 2
        # train model locally
        clf = LinearRegression()
        clf.fit(X, y)
        result = clf.predict(X)
        # store model in om
        self.om.models.put(clf, 'regression')
        # check we can use it to predict
        resp = self.client.put('/api/v1/model/regression/predict', json={
            'columns': ['v'],
            'data': dict(v=[5]),
        }, auth=self.auth, headers=self._async_headers)
        resp = self._check_async(resp)
        data = resp.get_json()['response']  # prediction result
        self.assertEqual(data.get('model'), 'regression')
        self.assertEqual(data.get('result'), [10.])

    def test_predict_from_dataset(self):
        X = np.arange(10).reshape(-1, 1)
        y = X * 2
        # train model locally
        clf = LinearRegression()
        clf.fit(X, y)
        result = clf.predict(X)
        # store model in om
        self.om.models.put(clf, 'regression')
        self.om.datasets.put([5], 'foo', append=False)
        # check we can use it to predict
        resp = self.client.put('/api/v1/model/regression/predict?datax=foo',
                               json={}, auth=self.auth, headers=self._async_headers)
        resp = self._check_async(resp)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()['response']
        self.assertEqual(data.get('model'), 'regression')
        self.assertEqual(data.get('result'), [10.])

    def test_predict_from_data_inline_versions(self):
        X = np.arange(10).reshape(-1, 1)
        y = X * 2
        # train model locally
        clf = LinearRegression()
        clf.fit(X, y)
        result = clf.predict(X)
        # store model in om
        self.om.models.put(clf, 'regression', tag='commit1')
        clf.intercept_ = 10
        self.om.models.put(clf, 'regression', tag='commit2')
        # check we can use it to predict previous version
        resp = self.client.put('/api/v1/model/regression^/predict', json={
            'columns': ['v'],
            'data': dict(v=[5]),
        }, auth=self.auth, headers=self._async_headers)
        resp = self._check_async(resp)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()['response']
        self.assertEqual(data.get('model'), 'regression^')
        assert_almost_equal(data.get('result'), [10.])
        # check we can use it to predict current version
        resp = self.client.put('/api/v1/model/regression/predict', json={
            'columns': ['v'],
            'data': dict(v=[5]),
        }, auth=self.auth, headers=self._headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get('model'), 'regression')
        assert_almost_equal(data.get('result'), [20.])
        # check we can use it to predict tagged version
        resp = self.client.put('/api/v1/model/regression@commit1/predict', json={
            'columns': ['v'],
            'data': dict(v=[5]),
        }, auth=self.auth, headers=self._headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get('model'), 'regression@commit1')
        assert_almost_equal(data.get('result'), [10.])

