import numpy as np
from sklearn.linear_model import LinearRegression

from omegaml import Omega
from omegaml.client.auth import OmegaRestApiAuth
from omegaml.restapi.app import app
from omegaml.restapi.tests.test_model_api import OmegaRestApiTests
from omegaml.restapi.tests.util import RequestsLikeTestClient


class OmegaRestApiTestsWithBuckets(OmegaRestApiTests):
    def setUp(self):
        self.client = RequestsLikeTestClient(app)
        self.om = Omega()['mybucket']
        self.auth = OmegaRestApiAuth('user', 'pass')
        self.clean()
        self.clean('mybucket')

    @property
    def _headers(self):
        return dict(bucket='mybucket')

    def test_default_bucket_fails(self):
        # put a model in the default bucket
        om = Omega()
        X = np.arange(10).reshape(-1, 1)
        y = X * 2
        # train model locally
        clf = LinearRegression()
        clf.fit(X, y)
        result = clf.predict(X)
        # store model in om
        om.models.put(clf, 'regression')
        resp = self.client.put('/api/v1/model/regression/predict', json={
            'columns': ['v'],
            'data': [dict(v=[5])],
        }, auth=self.auth, headers=self._headers)
        # we expect an error because the model does not exist in the default bucket
        self.assertEqual(resp.status_code, 400)
        # see if we can get it to predict with the correct bucket (all other tests do this)
        # -- note we simply remove the the 'bucket' header which reverts to the default
        resp = self.client.put('/api/v1/model/regression/predict', json={
            'columns': ['v'],
            'data': dict(v=[5])
        }, auth=self.auth)
        self.assertEqual(resp.status_code, 200)
