from landingpage.models import ServicePlan

from django.contrib.auth.models import User
from pandas.util.testing import assert_almost_equal
from sklearn.linear_model.base import LinearRegression
from sklearn.pipeline import Pipeline
from tastypie.test import ResourceTestCase

import numpy as np
from omegaml import Omega
from omegaops import add_user, add_service_deployment, get_client_config
import pandas as pd
from tastypiex.requesttrace import ClientRequestTracer


class ModelResourceTests(ResourceTestCase):

    def setUp(self):
        super(ModelResourceTests, self).setUp()
        #self.api_client = ClientRequestTracer(self.api_client)
        # setup django user
        self.username = username = 'test'
        self.email = email = 'test@omegaml.io'
        self.password = password = 'password'
        self.user = User.objects.create_user(username, email, password)
        self.apikey = self.user.api_key.key
        # setup omega credentials
        # FIXME refactor to remove dependency to landingpage (omegaweb should
        # have an injectable config module of sorts)
        ServicePlan.objects.create(name='omegaml')
        self.config = {
            'dbname': 'testdb',
            'username': self.user.username,
            'password': 'foobar',
        }
        add_user(self.config['dbname'], self.config['username'],
                 self.config['password'])
        add_service_deployment(self.user, self.config)
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

    def get_credentials(self):
        return self.create_apikey(self.username, self.apikey)

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
        self.assertHttpAccepted(resp)
        # predict
        resp = self.api_client.get(self.url('mymodel', 'predict', 'datax=X'),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        assert_almost_equal(data.get('result'), list(df['y'].astype(float)))

    def test_predict(self):
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
        resp = self.api_client.get(self.url('mymodel', 'predict', 'datax=X'),
                                   authentication=self.get_credentials())
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
        resp = self.api_client.get(self.url('mymodel', 'predict', 'datax=X'),
                                   authentication=self.get_credentials())
        self.assertHttpBadRequest(resp)
        # fit remotely
        resp = self.api_client.put(self.url('mymodel', 'fit',
                                            'datax=X&datay=Y'),
                                   data={},
                                   authentication=self.get_credentials())
        self.assertHttpAccepted(resp)
        # predict
        resp = self.api_client.get(self.url('mymodel', 'predict', 'datax=X'),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        assert_almost_equal(data.get('result'), list(df['y'].astype(float)))

    def test_partial_fit(self):
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
        resp = self.api_client.get(self.url('mymodel', 'predict', 'datax=X'),
                                   authentication=self.get_credentials())
        self.assertHttpBadRequest(resp)
        # fit remotely
        resp = self.api_client.put(self.url('mymodel', 'partial_fit',
                                            'datax=X&datay=Y'),
                                   data={},
                                   authentication=self.get_credentials())
        self.assertHttpAccepted(resp)
        # predict
        resp = self.api_client.get(self.url('mymodel', 'predict', 'datax=X'),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
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
        resp = self.api_client.get(self.url('mymodel', 'predict', 'datax=X'),
                                   authentication=self.get_credentials())
        self.assertHttpBadRequest(resp)
        # fit remotely
        resp = self.api_client.put(self.url('mymodel', 'fit',
                                            'datax=X&datay=Y'),
                                   data={},
                                   authentication=self.get_credentials())
        self.assertHttpAccepted(resp)
        # score
        resp = self.api_client.get(self.url('mymodel', 'score',
                                            'datax=X&datay=Y'),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        # fit locally for comparison
        p.fit(X, Y)
        score = p.score(X, Y)
        assert_almost_equal(data.get('result'), [score])

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
            ('lr', LinearRegression()),
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
        self.assertHttpAccepted(resp)
        # score
        resp = self.api_client.get(self.url('mymodel', 'transform',
                                            'datax=X'),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        assert_almost_equal(data.get('result'), [score])
