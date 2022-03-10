from __future__ import absolute_import

from unittest import TestCase

import numpy as np
import os
import pandas as pd
import sys
from numpy.testing import assert_array_almost_equal
from six.moves import range
from sklearn.datasets import make_classification
from sklearn.exceptions import NotFittedError
from sklearn.linear_model import LinearRegression
from sklearn.linear_model import LogisticRegression
from sklearn.linear_model import SGDRegressor
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.utils.validation import DataConversionWarning

from omegaml import Omega
from omegaml.backends.virtualobj import virtualobj
from omegaml.tests.util import OmegaTestMixin
from omegaml.util import delete_database, reshaped


class RuntimeTests(OmegaTestMixin, TestCase):

    def setUp(self):
        TestCase.setUp(self)
        om = self.om = Omega()
        self.clean()
        self.clean(bucket='test')

    def tearDown(self):
        TestCase.tearDown(self)

    def test_predict(self):
        # create some data
        x = np.array(list(range(0, 10)))
        y = x * 2
        df = pd.DataFrame({'x': x,
                           'y': y})
        X = df[['x']]
        Y = df[['y']]
        # put into Omega
        os.environ['DJANGO_SETTINGS_MODULE'] = ''
        om = Omega()
        om.runtime.celeryapp.conf.CELERY_ALWAYS_EAGER = True
        om.datasets.put(X, 'datax')
        om.datasets.put(Y, 'datay')
        om.datasets.get('datax')
        om.datasets.get('datay')
        # create a model locally, fit it, store in Omega
        lr = LinearRegression()
        lr.fit(X, Y)
        pred = lr.predict(X)
        om.models.put(lr, 'mymodel')
        self.assertIn('mymodel', om.models.list('*'))
        # have Omega predict it
        # -- using data already in Omega
        result = om.runtime.model('mymodel').predict('datax')
        pred1 = result.get()
        # -- using data provided locally
        #    note this is the same as
        #        om.datasets.put(X, 'foo')
        #        om.runtimes.model('mymodel').predict('foo')
        result = om.runtime.model('mymodel').predict(X)
        pred2 = result.get()
        self.assertTrue(
            (pred == pred1).all(), "runtimes prediction is different(1)")
        self.assertTrue(
            (pred == pred2).all(), "runtimes prediction is different(2)")

    def test_fit(self):
        # create some data
        x = np.array(list(range(0, 10)))
        y = x * 2
        df = pd.DataFrame({'x': x,
                           'y': y})
        X = df[['x']]
        Y = df[['y']]
        # put into Omega
        os.environ['DJANGO_SETTINGS_MODULE'] = ''
        om = Omega()
        om.runtime.celeryapp.conf.CELERY_ALWAYS_EAGER = True
        om.datasets.put(X, 'datax')
        om.datasets.put(Y, 'datay')
        om.datasets.get('datax')
        om.datasets.get('datay')
        # create a model locally, store (unfitted) in Omega
        lr = LinearRegression()
        om.models.put(lr, 'mymodel2')
        self.assertIn('mymodel2', om.models.list('*'))
        # predict locally for comparison
        lr.fit(X, Y)
        pred = lr.predict(X)
        # try predicting without fitting
        with self.assertRaises(NotFittedError):
            result = om.runtime.model('mymodel2').predict('datax')
            result.get()
        # have Omega fit the model then predict
        result = om.runtime.model('mymodel2').fit('datax', 'datay')
        result.get()
        # check the new model version metadata includes the datax/y references
        meta = om.models.metadata('mymodel2')
        self.assertIn('metaX', meta.attributes)
        self.assertIn('metaY', meta.attributes)
        # -- using data already in Omega
        result = om.runtime.model('mymodel2').predict('datax')
        pred1 = result.get()
        # -- using data provided locally
        #    note this is the same as
        #        om.datasets.put(X, 'foo')
        #        om.runtimes.model('mymodel2').predict('foo')
        result = om.runtime.model('mymodel2').fit(X, Y)
        result = om.runtime.model('mymodel2').predict(X)
        pred2 = result.get()
        # -- check the local data provided to fit was stored as intended
        meta = om.models.metadata('mymodel2')
        self.assertIn('metaX', meta.attributes)
        self.assertIn('metaY', meta.attributes)
        self.assertIn('_fitX', meta.attributes.get('metaX').get('name'))
        self.assertIn('_fitY', meta.attributes.get('metaY').get('name'))
        self.assertTrue(
            (pred == pred1).all(), "runtimes prediction is different(1)")
        self.assertTrue(
            (pred == pred2).all(), "runtimes prediction is different(2)")

    def test_partial_fit(self):
        # create some data
        x = np.array(list(range(0, 10)))
        y = x * 2
        df = pd.DataFrame({'x': x,
                           'y': y})
        X = df[['x']][0:2]
        Y = df[['y']][0:2]
        # put into Omega
        os.environ['DJANGO_SETTINGS_MODULE'] = ''
        om = Omega()
        om.runtime.celeryapp.conf.CELERY_ALWAYS_EAGER = True
        om.datasets.put(df[['x']], 'datax-full')
        om.datasets.put(X, 'datax')
        om.datasets.put(Y, 'datay')
        om.datasets.get('datax')
        om.datasets.get('datay')
        # create a model locally, store (unfitted) in Omega
        # -- ignore warnings on y shape
        import warnings
        warnings.filterwarnings("ignore", category=DataConversionWarning)
        lr = SGDRegressor(max_iter=1000, tol=1e-3)
        om.models.put(lr, 'mymodel2')
        # have Omega fit the model to get a start, then predict
        result = om.runtime.model('mymodel2').fit('datax', 'datay')
        result.get()
        # check the new model version metadata includes the datax/y references
        result = om.runtime.model('mymodel2').predict('datax-full')
        pred1 = result.get()
        mse = mean_squared_error(df.y, pred1)
        self.assertGreater(mse, 40)
        # fit mini batches add better training data, update model
        batch_size = 2
        for i, start in enumerate(range(0, len(df))):
            previous_mse = mse
            X = df[['x']][start:start + batch_size]
            Y = df[['y']][start:start + batch_size]
            om.datasets.put(X, 'datax-update', append=False)
            om.datasets.put(Y, 'datay-update', append=False)
            result = om.runtime.model('mymodel2').partial_fit(
                'datax-update', 'datay-update')
            result.get()
            # check the new model version metadata includes the datax/y
            # references
            result = om.runtime.model('mymodel2').predict('datax-full')
            pred1 = result.get()
            mse = mean_squared_error(df.y, pred1)
            self.assertLess(mse, previous_mse)

    def test_partial_fit_chunked(self):
        # create some data
        x = np.array(list(range(0, 100)))
        y = x * 2
        df = pd.DataFrame({'x': x,
                           'y': y})
        # put into Omega
        os.environ['DJANGO_SETTINGS_MODULE'] = ''
        om = Omega()
        om.runtime.celeryapp.conf.CELERY_ALWAYS_EAGER = True
        # generate a large dataset
        for i in range(100):
            om.datasets.put(df, 'data', append=(i > 0))
        # create a model locally, store (unfitted) in Omega
        # -- ignore warnings on y shape
        import warnings
        warnings.filterwarnings("ignore", category=DataConversionWarning)
        lr = SGDRegressor(max_iter=1000, tol=1e-3, random_state=42)
        om.models.put(lr, 'mymodel2')
        # have Omega fit the model to get a start, then predict
        result = om.runtime.model('mymodel2').fit(df[['x']], df[['y']])
        result.get()
        # check the new model version metadata includes the datax/y references
        result = om.runtime.model('mymodel2').predict('data[x]')
        pred1 = result.get()
        mse = mean_squared_error(om.datasets.get('data[y]'), pred1)
        self.assertGreater(mse, 40)
        # fit mini batches add better training data, update model
        result = om.runtime.model('mymodel2').partial_fit('data[x]#', 'data[y]#')
        result = om.runtime.model('mymodel2').predict('data[x]')
        pred1 = result.get()
        mse_2 = mean_squared_error(om.datasets.get('data[y]'), pred1)
        self.assertLess(mse_2, mse)

    def test_predict_pure_python(self):
        # create some data
        x = np.array(list(range(0, 10)))
        y = x * 2
        df = pd.DataFrame({'x': x,
                           'y': y}).astype('O')
        X = [[x] for x in list(df.x)]
        Y = [[y] for y in list(df.y)]
        # put into Omega -- assume a client with pandas, scikit learn
        os.environ['DJANGO_SETTINGS_MODULE'] = ''
        om = Omega()
        om.runtime.pure_python = True
        om.runtime.celeryapp.conf.CELERY_ALWAYS_EAGER = True
        om.datasets.put(X, 'datax')
        om.datasets.put(Y, 'datay')
        Xhat = om.datasets.get('datax')
        Yhat = om.datasets.get('datay')
        self.assertEqual([X], Xhat)
        self.assertEqual([Y], Yhat)
        # have Omega fit the model then predict
        lr = LinearRegression()
        lr.fit(X, Y)
        pred = lr.predict(X)
        om.models.put(lr, 'mymodel2')
        # -- using data provided locally
        #    note this is the same as
        #        om.datasets.put(X, 'foo')
        #        om.runtimes.model('mymodel2').predict('foo')
        result = om.runtime.model('mymodel2').predict(reshaped(X))
        pred2 = result.get()
        self.assertTrue(
            (pred == pred2).all(), "runtimes prediction is different(1)")
        self.assertTrue(
            (pred == pred2).all(), "runtimes prediction is different(2)")

    def test_predict_hdf_dataframe(self):
        # create some data
        x = np.array(list(range(0, 10)))
        y = x * 2
        df = pd.DataFrame({'x': x,
                           'y': y})
        X = df['x']
        Y = df['y']
        # put into Omega -- assume a client with pandas, scikit learn
        os.environ['DJANGO_SETTINGS_MODULE'] = ''
        om = Omega()
        om.runtime.pure_python = True
        om.runtime.celeryapp.conf.CELERY_ALWAYS_EAGER = True
        om.datasets.put(X, 'datax', as_hdf=True)
        om.datasets.put(Y, 'datay', as_hdf=True)
        # have Omega fit the model then predict
        lr = LinearRegression()
        lr.fit(reshaped(X), reshaped(Y))
        pred = lr.predict(reshaped(X))
        om.models.put(lr, 'mymodel2')
        # -- using data provided locally
        #    note this is the same as
        #        om.datasets.put(X, 'foo')
        #        om.runtimes.model('mymodel2').predict('foo')
        result = om.runtime.model('mymodel2').predict('datax')
        pred2 = result.get()
        self.assertTrue(
            (pred == pred2).all(), "runtimes prediction is different(1)")
        self.assertTrue(
            (pred == pred2).all(), "runtimes prediction is different(2)")

    def test_fit_pipeline(self):
        # create some data
        x = np.array(list(range(0, 10)))
        y = x * 2
        df = pd.DataFrame({'x': x,
                           'y': y})
        X = df[['x']]
        Y = df[['y']]
        # put into Omega
        os.environ['DJANGO_SETTINGS_MODULE'] = ''
        om = Omega()
        om.runtime.celeryapp.conf.CELERY_ALWAYS_EAGER = True
        om.datasets.put(X, 'datax')
        om.datasets.put(Y, 'datay')
        om.datasets.get('datax')
        om.datasets.get('datay')
        # create a pipeline locally, store (unfitted) in Omega
        p = Pipeline([
            ('lr', LinearRegression()),
        ])
        om.models.put(p, 'mymodel2')
        self.assertIn('mymodel2', om.models.list('*'))
        # predict locally for comparison
        p.fit(reshaped(X), reshaped(Y))
        pred = p.predict(reshaped(X))
        # have Omega fit the model then predict
        result = om.runtime.model('mymodel2').fit('datax', 'datay')
        result.get()
        result = om.runtime.model('mymodel2').predict('datax')
        pred1 = result.get()
        self.assertTrue(
            (pred == pred1).all(), "runtimes prediction is different(1)")

    def test_score(self):
        # create some data
        x = np.array(list(range(0, 10)))
        y = x * 2
        df = pd.DataFrame({'x': x,
                           'y': y})
        X = df[['x']]
        Y = df[['y']]
        # put into Omega
        os.environ['DJANGO_SETTINGS_MODULE'] = ''
        om = Omega()
        om.runtime.celeryapp.conf.CELERY_ALWAYS_EAGER = True
        om.datasets.put(X, 'datax')
        om.datasets.put(Y, 'datay')
        om.datasets.get('datax')
        om.datasets.get('datay')
        # create a model locally, fit it, store in Omega
        lr = LinearRegression()
        lr.fit(X, Y)
        scores = lr.score(X, Y)
        om.models.put(lr, 'mymodel')
        # fit in omegaml
        r_scores = om.runtime.model('mymodel').score('datax', 'datay').get()
        self.assertEqual(scores, r_scores)

    def test_gridsearch(self):
        X, y = make_classification()
        logreg = LogisticRegression(solver='liblinear')
        os.environ['DJANGO_SETTINGS_MODULE'] = ''
        om = Omega()
        om.runtime.celeryapp.conf.CELERY_ALWAYS_EAGER = True
        om.models.put(logreg, 'logreg')
        params = {
            'C': [0.1, 0.5, 1.0]
        }
        # gridsearch on runtimes
        om.runtime.model('logreg').gridsearch(X, y, parameters=params).get()
        meta = om.models.metadata('logreg')
        # check gridsearch was saved
        self.assertIn('gridsearch', meta.attributes)
        self.assertEqual(len(meta.attributes['gridsearch']), 1)
        self.assertIn('gsModel', meta.attributes['gridsearch'][0])
        # check we can get back the gridsearch model
        gs_model = om.models.get(meta.attributes['gridsearch'][0]['gsModel'])
        self.assertIsInstance(gs_model, GridSearchCV)

    def test_gridsearch_iris(self):
        om = Omega()
        from sklearn.datasets import load_iris
        X, y = load_iris(return_X_y=True)
        df = pd.DataFrame(X)
        df['y'] = y
        om.datasets.put(df, 'iris', append=False)
        from sklearn.cluster import KMeans
        model = KMeans(n_clusters=8)
        # fit & predict remote
        om.models.drop('iris-model', True)
        om.models.put(model, 'iris-model')
        om.runtime.model('iris-model').fit(X, y).get()
        params = {
            'n_clusters': range(1, 8),
        }
        om.runtime.model('iris-model').gridsearch('iris[^y]', 'iris[y]', parameters=params).get()

    def test_ping(self):
        om = Omega()
        result = om.runtime.ping(fox='bar')
        self.assertIn('message', result)
        self.assertIn('worker', result)
        self.assertEqual(result['kwargs'], dict(fox='bar'))

    def test_task_sequence(self):
        om = Omega()
        df = pd.DataFrame({'x': range(1, 10),
                           'y': range(5, 14)})
        lr = LinearRegression()
        om.datasets.put(df, 'sample')
        om.models.put(lr, 'regmodel')
        with om.runtime.sequence() as ctr:
            ctr.ping(wait=False)
            ctr.model('regmodel').fit('sample[x]', 'sample[y]')
            ctr.model('regmodel').predict('sample[x]')
            result = ctr.run()

        data = result.get()
        assert_array_almost_equal(df['y'].values, data[:, 0])

    def test_task_parallel(self):
        om = Omega()
        df = pd.DataFrame({'x': range(1, 10),
                           'y': range(5, 14)})
        lr = LinearRegression()
        om.datasets.put(df, 'sample')
        om.models.put(lr, 'regmodel')
        om.runtime.model('regmodel').fit('sample[x]', 'sample[y]').get()
        with om.runtime.parallel() as ctr:
            ctr.model('regmodel').predict('sample[x]')
            ctr.model('regmodel').predict('sample[x]')
            result = ctr.run()

        data = result.get()
        assert_array_almost_equal(df['y'].values, data[0][:, 0])
        assert_array_almost_equal(df['y'].values, data[1][:, 0])

    def test_task_mapreduce_virtualfn(self):
        om = Omega()
        df = pd.DataFrame({'x': range(1, 10),
                           'y': range(5, 14)})
        lr = LinearRegression()
        om.datasets.put(df, 'sample')
        om.models.put(lr, 'regmodel')
        om.runtime.model('regmodel').fit('sample[x]', 'sample[y]').get()

        @virtualobj
        def combined(data=None, method=None, meta=None, store=None, **kwargs):
            # data is the list of results from the previous tasks
            # we scale results to verify combined actually runs
            return [y * 5 for y in data]

        om.models.put(combined, 'combined')
        with om.runtime.mapreduce() as ctr:
            # two tasks to map
            ctr.model('regmodel').predict('sample[x]')
            ctr.model('regmodel').predict('sample[x]')
            # one task to reduce
            ctr.model('combined').reduce()
            result = ctr.run()

        data = result.get()
        assert_array_almost_equal(df['y'].values * 5, data[0][:, 0])
        assert_array_almost_equal(df['y'].values * 5, data[1][:, 0])

        @virtualobj
        def combined(data=None, method=None, meta=None, store=None, **kwargs):
            # data is the list of results from the previous tasks
            # we return only one result, simulating selection
            return data[0][:, 0]

        om.models.put(combined, 'combined', replace=True)
        with om.runtime.mapreduce() as ctr:
            # two tasks to map
            ctr.model('regmodel').predict('sample[x]')
            ctr.model('regmodel').predict('sample[x]')
            # one task to reduce
            ctr.model('combined').reduce()
            result = ctr.run()

        data = result.get()
        assert_array_almost_equal(df['y'].values, data)

    def test_task_mapreduce_script(self):
        om = Omega()
        df = pd.DataFrame({'x': range(1, 10),
                           'y': range(5, 14)})
        lr = LinearRegression()
        om.datasets.put(df, 'sample')
        om.models.put(lr, 'regmodel')
        om.runtime.model('regmodel').fit('sample[x]', 'sample[y]').get()

        om = Omega()
        basepath = os.path.join(os.path.dirname(sys.modules['omegaml'].__file__), 'example')
        pkgpath = os.path.abspath(os.path.join(basepath, 'demo', 'callback'))
        pkgsrc = 'pkg://{}'.format(pkgpath)
        om.scripts.put(pkgsrc, 'callback')
        with om.runtime.mapreduce() as ctr:
            # two tasks to map
            ctr.model('regmodel').predict('sample[x]')
            ctr.model('regmodel').predict('sample[x]')
            # one task to reduce
            ctr.script('callback').run(as_callback=True)
            result = ctr.run()

        result.get()
        self.assertEqual(len(om.datasets.get('callback_results')), 2)

        with om.runtime.mapreduce() as ctr:
            # two tasks to map
            ctr.model('regmodel').predict('sample[x]')
            # one task to reduce
            ctr.script('callback').run(as_callback=True)
            result = ctr.run()

        result.get()
        self.assertEqual(len(om.datasets.get('callback_results')), 3)

    def test_task_callback(self):
        om = Omega()
        basepath = os.path.join(os.path.dirname(sys.modules['omegaml'].__file__), 'example')
        pkgpath = os.path.abspath(os.path.join(basepath, 'demo', 'callback'))
        pkgsrc = 'pkg://{}'.format(pkgpath)
        om.scripts.put(pkgsrc, 'callback')
        df = pd.DataFrame({'x': range(1, 10),
                           'y': range(5, 14)})
        lr = LinearRegression()
        lr.fit(df[['x']], df['y'])
        om.datasets.put(df, 'sample')
        om.models.put(lr, 'regmodel')
        result = (om.runtime
                  .callback('callback')
                  .model('regmodel')
                  .predict('sample[x]')
                  .get())
        self.assertEqual(len(om.datasets.get('callback_results')), 1)
        result = (om.runtime
                  .callback('callback')
                  .model('regmodel')
                  .predict('sample[x]')
                  .get())
        self.assertEqual(len(om.datasets.get('callback_results')), 2)

    def test_task_callback_bucket(self):
        om = Omega()
        omb = om['test']
        basepath = os.path.join(os.path.dirname(sys.modules['omegaml'].__file__), 'example')
        pkgpath = os.path.abspath(os.path.join(basepath, 'demo', 'callback'))
        pkgsrc = 'pkg://{}'.format(pkgpath)
        omb.scripts.put(pkgsrc, 'callback')
        df = pd.DataFrame({'x': range(1, 10),
                           'y': range(5, 14)})
        lr = LinearRegression()
        lr.fit(df[['x']], df['y'])
        omb.datasets.put(df, 'sample')
        omb.models.put(lr, 'regmodel')
        result = (omb.runtime
                  .callback('callback')
                  .model('regmodel')
                  .predict('sample[x]')
                  .get())
        self.assertEqual(len(omb.datasets.get('callback_results')), 1)
        result = (omb.runtime
                  .callback('callback')
                  .model('regmodel')
                  .predict('sample[x]')
                  .get())
        self.assertEqual(len(omb.datasets.get('callback_results')), 2)

    def test_task_logging(self):
        """ test task python output can be logged per-request """
        om = Omega()
        om.logger.reset()
        # no python logging, only om.logger
        om.runtime.ping(fox='bar', logging=False)
        self.assertEqual(len(om.logger.dataset.get(level='INFO')), 0)
        # python log capture, we get om.logger, omegaml + stdout log
        om.logger.reset()
        om.runtime.mode(logging=True).ping(fox='bar')
        self.assertEqual(len(om.logger.dataset.get(level='INFO')), 4)
        # specific python logger, we get om.logger + celery
        om.logger.reset()
        om.runtime.mode(logging='celery').ping(fox='bar')
        self.assertEqual(len(om.logger.dataset.get(level='INFO')), 3)
        # request a different level, we get celery + stdout
        om.logger.reset()
        om.runtime.mode(logging=('celery', 'DEBUG')).ping(fox='bar')
        self.assertEqual(len(om.logger.dataset.get()), 4)

    def test_task_logging_bucket(self):
        """ test task python output can be logged per-request """
        om = Omega()['test']
        om.logger.reset()
        # no python logging, only om.logger
        om.runtime.ping(fox='bar', logging=False)
        self.assertEqual(len(om.logger.dataset.get(level='INFO')), 0)
        # python log capture, we get om.logger, omegaml + stdout log
        om.logger.reset()
        om.runtime.mode(logging=True).ping(fox='bar')
        self.assertEqual(len(om.logger.dataset.get(level='INFO')), 4)
        # specific python logger, we get om.logger, celery + stdout log
        om.logger.reset()
        om.runtime.mode(logging='celery').ping(fox='bar')
        self.assertEqual(len(om.logger.dataset.get(level='INFO')), 3)
        # request a different level, we get celery + stdout
        om.logger.reset()
        om.runtime.mode(logging=('celery', 'DEBUG')).ping(fox='bar')
        self.assertEqual(len(om.logger.dataset.get()), 4)

    def test_logging_mode(self):
        """ test task python output can be logged for all requests """
        om = Omega()
        om.logger.reset()
        # -- request logging
        om.runtime.mode(local=True, logging=True)
        om.runtime.ping(fox='bar')
        self.assertEqual(len(om.logger.dataset.get(level='INFO')), 4)
        # -- switch off logging
        om.logger.reset()
        om.runtime.mode(local=True, logging=False)
        om.runtime.ping(fox='bar')
        self.assertEqual(len(om.logger.dataset.get(level='INFO')), 0)
        # -- request specific logger
        om.logger.reset()
        om.runtime.mode(local=True, logging=('celery', 'DEBUG'))
        om.runtime.ping(fox='bar')
        self.assertEqual(len(om.logger.dataset.get(level='DEBUG')), 3)
