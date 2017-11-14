from tastypie.test import ResourceTestCase

import numpy as np
import omegaml as om
import pandas as pd
from sklearn.linear_model.base import LinearRegression
from sklearn.pipeline import Pipeline
from pandas.util.testing import assert_almost_equal


class ModelResourceTests(ResourceTestCase):

    def setUp(self):
        super(ModelResourceTests, self).setUp()
        self.om = om
        om.runtime.celeryapp.conf.CELERY_ALWAYS_EAGER = True
        for ds in om.datasets.list():
            om.datasets.drop(ds)

    def tearDown(self):
        pass

    def url(self, pk=None, query=None):
        url = '/api/v1/model/'
        if pk is not None:
            url += pk + '/'
        if query is not None:
            url += '?{query}'.format(**locals())
        return url

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
        resp = self.api_client.get(self.url('mymodel', 'datax=X'))
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
        resp = self.api_client.get(self.url('mymodel', 'datax=X'))
        self.assertHttpBadRequest(resp)
        # fit remotely
        resp = self.api_client.put(self.url('mymodel', 'datax=X&datay=Y'),
                                   data={})
        data = self.deserialize(resp)
        # predict
        self.assertHttpAccepted(resp)
        resp = self.api_client.get(self.url('mymodel', 'datax=X'))
        data = self.deserialize(resp)
        assert_almost_equal(data.get('result'), list(df['y'].astype(float)))
