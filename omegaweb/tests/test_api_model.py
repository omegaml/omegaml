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


class ModelResourceTests(ResourceTestCase):

    def setUp(self):
        super(ModelResourceTests, self).setUp()
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

    def url(self, pk=None, query=None):
        url = '/api/v1/model/'
        if pk is not None:
            url += pk + '/'
        if query is not None:
            url += '?{query}'.format(**locals())
        return url

    def get_credentials(self):
        return self.create_apikey(self.username, self.apikey)

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
        resp = self.api_client.get(self.url('mymodel', 'datax=X'),
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
        resp = self.api_client.get(self.url('mymodel', 'datax=X'),
                                   authentication=self.get_credentials())
        self.assertHttpBadRequest(resp)
        # fit remotely
        resp = self.api_client.put(self.url('mymodel', 'datax=X&datay=Y'),
                                   data={},
                                   authentication=self.get_credentials())
        self.assertHttpAccepted(resp)
        # predict
        resp = self.api_client.get(self.url('mymodel', 'datax=X'),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        assert_almost_equal(data.get('result'), list(df['y'].astype(float)))
