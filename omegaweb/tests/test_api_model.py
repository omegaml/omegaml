from unittest import mock

import numpy as np
import os
import pandas as pd
from django.contrib.auth.models import User, Group
from django.test import TestCase
from pandas._testing import assert_almost_equal
from sklearn.linear_model import LinearRegression
from sklearn.linear_model import SGDRegressor, LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from tastypie.authentication import ApiKeyAuthentication
from tastypie.serializers import Serializer
from tastypie.test import ResourceTestCaseMixin
from tastypie.throttle import BaseThrottle
from unittest.mock import patch

from landingpage.authz import RolePermissionsAuthorization
from landingpage.models import PermissionedResource
from landingpage.permutil import PermissionUtil
from omegaml import Omega
from omegaml.sklext import OnlinePipeline
from omegaops import get_client_config
from omegaweb.resources import ModelResource
from omegaweb.tests.util import OmegaResourceTestMixin


# ensure the client uses the server-specified mongo url
@mock.patch.dict(os.environ, {"OMEGA_MONGO_URL": ""})
class ModelResourceTests(OmegaResourceTestMixin, ResourceTestCaseMixin, TestCase):
    fixtures = ['landingpage']

    def setUp(self):
        super(ModelResourceTests, self).setUp()
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

    def get_credentials(self, user=None):
        user = user or self.user
        return self.create_apikey(user.username, user.api_key.key)

    def test_get_modelinfo(self):
        om = self.om
        p = Pipeline([
            ('lr', LinearRegression()),
        ])
        om.models.put(p, 'mymodel')
        resp = self.api_client.get(self.url('mymodel'),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertIn('model', data)
        self.assertIn('bucket', data['model'])
        self.assertIn('name', data['model'])
        self.assertIn('kind', data['model'])
        self.assertIn('created', data['model'])

    def test_create_model(self):
        om = self.om
        data = {
            'name': 'mymodel',
            'pipeline': [
                # step name, model class, kwargs
                ['LinearRegression', dict()],
            ],
        }
        resp = self.api_client.post(self.url(),
                                    data=data,
                                    authentication=self.get_credentials())
        self.assertHttpCreated(resp)
        data = self.deserialize(resp)
        self.assertIn('model', data)
        self.assertIn('created', data['model'])
        # try to fit
        x = np.array(list(range(1, 100)))
        y = x * 2
        df = pd.DataFrame({'x': x,
                           'y': y})
        X = df[['x']]
        Y = df[['y']]
        om.datasets.put(X, 'X', append=False)
        om.datasets.put(Y, 'Y', append=False)
        # fit remotely
        resp = self.api_client.put(self.url('mymodel', 'fit',
                                            'datax=X&datay=Y'),
                                   data={},
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        # predict
        resp = self.api_client.put(self.url('mymodel', 'predict', 'datax=X'),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        assert_almost_equal(data.get('result'), list(df['y'].astype(float)))

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
                                   authentication=self.get_credentials())
        self.assertEqual(resp.status_code, 200)
        data = self.deserialize(resp)
        assert_almost_equal(data.get('result'), list(df['y'].astype(float)))

    def test_predict_from_dataset_model_path(self):
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
        om.models.put(p, 'some/foo/mymodel')
        resp = self.api_client.put(self.url('some/foo/mymodel', 'predict', 'datax=X'),
                                   authentication=self.get_credentials())
        self.assertEqual(resp.status_code, 200)
        data = self.deserialize(resp)
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
                                   authentication=self.get_credentials())
        self.assertEqual(resp.status_code, 200)
        data = self.deserialize(resp)
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
                                   authentication=self.get_credentials())
        self.assertHttpBadRequest(resp)
        # fit remotely
        resp = self.api_client.put(self.url('mymodel', 'fit',
                                            'datax=X&datay=Y'),
                                   data={},
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        # predict
        resp = self.api_client.put(self.url('mymodel', 'predict', 'datax=X'),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        assert_almost_equal(data.get('result'), list(df['y'].astype(float)))

    def test_partial_fit(self):
        om = self.om
        # we use a large dataset to speed up the test
        # -- this way we only have to partial fit 1-2 times to get a good result
        # -- SGDRegressor updates weights for every sample (not epoch)
        # -- see https://scikit-learn.org/stable/modules/sgd.html#id5
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
                                  penalty='l1', max_iter=10, tol=1e-3)),
        ])
        om.models.put(p, 'mymodel')
        # try to predict without fitting
        resp = self.api_client.put(self.url('mymodel', 'predict', 'datax=X'),
                                   authentication=self.get_credentials())
        self.assertHttpBadRequest(resp)
        # preform initial fit to speed up the test
        p.fit(X, Y)
        n_iter = 2
        for i in range(n_iter):
            resp = self.api_client.put(self.url('mymodel', 'partial_fit',
                                                'datax=X&datay=Y'),
                                       data={},
                                       authentication=self.get_credentials())
            self.assertHttpOK(resp)
        # predict
        resp = self.api_client.put(self.url('mymodel', 'predict', 'datax=X'),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        assert_almost_equal(data.get('result'), list(df['y'].astype(float)),
                            atol=1, rtol=1)

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
                                   authentication=self.get_credentials())
        self.assertHttpBadRequest(resp)
        # fit remotely
        resp = self.api_client.put(self.url('mymodel', 'fit',
                                            'datax=X&datay=Y'),
                                   data={},
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        # score
        resp = self.api_client.get(self.url('mymodel', 'score',
                                            'datax=X&datay=Y'),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
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
                                   authentication=self.get_credentials())
        self.assertHttpBadRequest(resp)
        # fit remotely
        resp = self.api_client.put(self.url('mymodel', 'fit',
                                            'datax=X&datay=Y'),
                                   data={},
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        # score
        resp = self.api_client.get(self.url('mymodel', 'transform',
                                            'datax=X'),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
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
                                   authentication=self.get_credentials())
        self.assertHttpBadRequest(resp)
        # fit remotely
        resp = self.api_client.put(self.url('mymodel', 'fit',
                                            'datax=X&datay=Y'),
                                   data={},
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        # score
        resp = self.api_client.get(self.url('mymodel', 'decision_function',
                                            'datax=X'),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        # do the same locally
        p.fit(X, Y)
        local_result = p.decision_function(X).flatten().tolist()
        assert_almost_equal(data.get('result'), local_result)

    def test_model_api_permissions(self):
        """
        test client config is only accessible when permissioned
        """
        # set up permissions
        res = PermissionedResource.objects.create(uri='/api/v1/model', actions='list,predict', methods='get,put')
        Group.objects.create(name='service_user')
        res.allow('service_user')
        user = self.user  # User.objects.create_user('john', 'john@example.com')
        with patch.object(ModelResource, '_meta') as api_meta:
            # mock the api meta
            # -- we do it like this because we don't have a way to set the meta on the actual resource
            api_meta.authentication = ApiKeyAuthentication()
            api_meta.authorization = RolePermissionsAuthorization()
            api_meta.list_allowed_methods = ['get']
            api_meta.throttle = BaseThrottle()
            api_meta.serializer = Serializer()
            # get config from api
            # -- expect failure (user is not member of service_user)
            auth = self.get_credentials(user=user)
            # -- list
            resp = self.api_client.get(self.url(), authentication=auth)
            self.assertEqual(resp.status_code, 401)
            # -- predict
            resp = self.api_client.get(self.url(pk='foo', action='predict'), authentication=auth)
            self.assertEqual(resp.status_code, 401)
            # get config from api
            # -- expect works ok (user is member of service_user)
            PermissionUtil.assign_role(self.user, 'service_user')
            auth = self.get_credentials(user=user)
            resp = self.api_client.get(self.url(), authentication=auth)
            self.assertHttpOK(resp)
            resp = self.api_client.get(self.url(pk='foo', action='predict'), authentication=auth)
            # -- permission is ok, but object foo does not exist
            self.assertHttpBadRequest(resp)
            resp = self.api_client.put(self.url(pk='foo', action='predict'), authentication=auth)
            # -- permission is ok, but object foo does not exist
            self.assertHttpBadRequest(resp)
            # remove permission
            # -- expect failure (user is not member of service_user)
            res.deny('service_user')
            auth = self.get_credentials(user=user)
            resp = self.api_client.get(self.url(), authentication=auth)
            self.assertEqual(resp.status_code, 401)
            resp = self.api_client.get(self.url(pk='foo', action='predict'), authentication=auth)
            self.assertEqual(resp.status_code, 401)
            resp = self.api_client.put(self.url(pk='foo', action='predict'), authentication=auth)
            self.assertEqual(resp.status_code, 401)
            # try creating
            resp = self.api_client.post(self.url(), authentication=auth)
            self.assertEqual(resp.status_code, 401)
