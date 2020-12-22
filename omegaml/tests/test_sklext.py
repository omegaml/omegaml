from unittest.case import TestCase

import numpy as np
from sklearn.datasets import make_regression
from sklearn.linear_model import SGDRegressor
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from omegaml.sklext import OnlinePipeline


class OnlinePipelineTests(TestCase):
    def test_partial_fit(self):
        # define an online pipeline
        piple = OnlinePipeline([
            ('scale', StandardScaler()),
            ('clf', SGDRegressor(random_state=5, shuffle=False, verbose=True, max_iter=10)),
        ])
        # define an offline pipelines
        pipl = Pipeline([
            ('scale', StandardScaler()),
            ('clf', SGDRegressor(random_state=5, shuffle=False, verbose=True, max_iter=20)),
        ])
        # generate some data
        X, y = make_regression(100, 100, random_state=42)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=.33, random_state=42)
        # fit, predict in an online manner
        for i in range(100):
            piple.partial_fit(X_train[0:30], y_train[0:30])
            piple.partial_fit(X_train[30:], y_train[30:])
        ye = piple.predict(X_test)
        # fit, predict in offline manner
        pipl.fit(X_train, y_train)
        yh = pipl.predict(X_test)
        # compare results
        r2_offline = r2_score(y_test, yh)
        r2_online = r2_score(y_test, ye)
        # use a relatively high tolerance due to differences in results of offline and online
        np.testing.assert_allclose(r2_offline, r2_online, atol=0.1)
