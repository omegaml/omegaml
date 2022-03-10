from time import sleep

import platform

import pandas as pd
import unittest
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression

from omegaml import Omega
from omegaml.backends.experiment import ExperimentBackend, OmegaSimpleTracker, OmegaProfilingTracker
from omegaml.documents import Metadata
from omegaml.tests.util import OmegaTestMixin


class TrackingTestCases(OmegaTestMixin, unittest.TestCase):
    def setUp(self):
        self.om = om = Omega()
        self.clean()
        om.models.register_backend(ExperimentBackend.KIND, ExperimentBackend)

    def test_ensure_active(self):
        # explicit start
        om = self.om
        exp = om.runtime.experiment('test')
        with self.assertRaises(ValueError):
            exp.log_param('foo', 'bar')
        run = exp.start()
        exp.log_param('foo', 'bar')
        data = exp.data(run=run)
        self.assertIsNotNone(run)
        self.assertEqual(len(data), 3)
        # reuse latest run
        exp = om.runtime.experiment('test')
        with self.assertRaises(ValueError):
            exp.log_param('foo', 'bar')
        exp.use()
        exp.log_param('foo', 'bar')
        data = exp.data(run=run)
        self.assertIsNotNone(run)
        self.assertEqual(len(data), 4)
        # implied run should be NOT set in with block if use() was called previously
        # rationale: with exp should always start a new run
        with exp as xexp:
            xexp.log_param('foo', 'bar')
        data = xexp.data()
        self.assertEqual(len(data), 4)
        self.assertEqual(set(data['event']), set(['start', 'stop', 'param', 'system']))
        self.assertEqual(data['run'].iloc[-1], run + 1)

    def test_simple_tracking(self):
        # create a model
        om = self.om
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression(solver='liblinear', multi_class='auto')
        lr.fit(X, Y)
        # run a local experiment and track its result
        with om.runtime.experiment('myexp') as exp:
            score = lr.score(X, Y)
            exp.log_metric('accuracy', score)
        # check the experiemnt is logged
        self.assertIn('experiments/myexp', om.models.list('experiments/*'))
        exp = om.models.get('experiments/myexp', data_store=om.datasets)
        data = exp.data(event='metric')
        self.assertIsInstance(exp, OmegaSimpleTracker)
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data.iloc[0]['key'], 'accuracy')
        self.assertEqual(data.iloc[0]['value'], score)
        # get back the tracker as an object
        tracker = om.models.get('experiments/myexp', raw=True, data_store=om.datasets)
        self.assertIsInstance(tracker, OmegaSimpleTracker)
        # check remote execution of experiement
        # -- we want to easily transfer code execution to a remote
        # -- while keeping the code semantics as local as possible
        om.models.put(lr, 'mymodel')
        with om.runtime.experiment('myexp', provider='simple') as exp:
            om.runtime.model('mymodel').fit(X, Y)
            om.runtime.model('mymodel').score(X, Y)
            exp.log_metric('accuracy', 1)
            exp.log_artifact(lr, 'mymodel')
            exp.log_artifact(om.models.metadata('mymodel'), 'mymodel_meta')
        tracker = om.models.get('experiments/myexp', raw=True, data_store=om.datasets)
        data = tracker.data()
        self.assertIsInstance(data, pd.DataFrame)
        self.assertEqual(len(data), 17)  # includes runtime task events
        self.assertEqual(len(data[data.event == 'start']), 2)
        self.assertEqual(len(data[data.event == 'stop']), 2)
        self.assertEqual(len(data[data.event == 'artifact']), 4)
        artifacts = data[data.event == 'artifact']['value'].to_list()
        obj = exp.restore_artifact(key='mymodel')
        self.assertIsInstance(obj, LogisticRegression)
        obj = exp.restore_artifact(key='mymodel_meta')
        self.assertIsInstance(obj, Metadata)
        # related is stored by runtime automatically as the delegate's metadata
        obj = exp.restore_artifact(key='related')
        self.assertIsInstance(obj, Metadata)
        # check that the current metadata lists the experiment for tracability
        meta = om.models.metadata('mymodel')
        self.assertIn('myexp', meta.attributes['tracking']['experiments'])

    def test_tracking_from_metadata(self):
        # create a model
        om = self.om
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression(solver='liblinear', multi_class='auto')
        lr.fit(X, Y)
        om.models.put(lr, 'mymodel')
        # no tracking
        tracker = om.runtime.experiment('expfoo')
        exp = tracker.experiment
        data = exp.data()
        self.assertIsNone(data)
        # implicit tracking via metadata
        om.models.put(lr, 'mymodel', attributes={
            'tracking': {
                'default': 'expfoo2',
            }})
        om.runtime.model('mymodel').score(X, Y)
        tracker = om.runtime.experiment('expfoo2')
        exp = tracker.experiment
        data = exp.data()
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 6)

    def test_tracking_predictions(self):
        # create a model
        om = self.om
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression(solver='liblinear', multi_class='auto')
        lr.fit(X, Y)
        om.models.put(lr, 'mymodel', attributes={
            'tracking': {
                'default': 'expfoo'
            }
        })
        om.runtime.model('mymodel').score(X, Y)
        tracker = om.runtime.experiment('expfoo')
        exp = tracker.experiment
        data = exp.data()
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 6)

    def test_empty_experiment_data(self):
        om = self.om
        with om.runtime.experiment('myexp') as exp:
            pass
        exp = om.models.get('experiments/myexp', data_store=om.datasets)
        # we have at least a 'system' event
        self.assertEqual(len(exp.data(event='metric')), 0)
        self.assertEqual(len(exp.data()), 3)  # system, start, stop events

    def test_experiment_explicit_logging(self):
        om = self.om
        with om.runtime.experiment('myexp') as exp:
            exp.log_metric('accuracy', .98)
        exp = om.models.get('experiments/myexp', data_store=om.datasets)
        self.assertEqual(len(exp.data(event='metric')), 1)

    def test_experiments_not_versioned(self):
        om = self.om
        with om.runtime.experiment('myexp') as exp:
            pass
        meta = om.models.metadata('experiments/myexp')
        self.assertNotIn('versions', meta.attributes)

    def test_experiment_artifact(self):
        om = self.om
        with om.runtime.experiment('myexp') as exp:
            exp.log_artifact(dict(test='data'), 'foo')
        # by name
        data = exp.restore_artifact('foo')
        self.assertIsInstance(data, dict)
        # by value
        data = exp.data(key='foo')
        data = exp.restore_artifact(value=data.iloc[0].value)

    def test_notrack(self):
        # create a model
        om = self.om
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression(solver='liblinear', multi_class='auto')
        lr.fit(X, Y)
        # use runtime to fit model without tracking
        om.models.put(lr, 'mymodel')
        om.runtime.model('mymodel').fit(X, Y)
        tracker = om.runtime.experiment('exp')
        exp = tracker.experiment
        # no tracking, no data
        data = exp.data()
        self.assertIsNone(data)

    def test_experiment_existing_model(self):
        om = self.om
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression(solver='liblinear', multi_class='auto')
        om.models.put(lr, 'foo')
        with om.runtime.experiment('experiments/foo') as exp:
            exp.log_metric(5, 'accuracy')
        self.assertIn('experiments/foo', om.models.list())

    def test_drop_experiment(self):
        om = self.om
        # create experiment, add some data
        with om.runtime.experiment('foo') as exp:
            exp.log_metric(5, 'accuracy')
        self.assertEqual(len(exp.data()), 4)
        # check experiment and data where created
        self.assertIn('experiments/foo', om.models.list())
        meta = om.models.metadata('experiments/foo')
        dataset = meta.attributes.get('dataset')
        self.assertIsNotNone(dataset)
        self.assertIn(dataset, om.datasets.list(hidden=True))
        self.assertIn('experiments/foo', om.models.list())
        # add a metric, then clean
        exp.log_metric(5, 'accuracy')
        self.assertEqual(len(exp.data()), 5)
        # explicit drop
        om.models.drop('experiments/foo', data_store=om.datasets)
        self.assertNotIn(dataset, om.datasets.list(hidden=True))
        # no more data present
        self.assertIsNone(exp.data())

    def test_log_system(self):
        om = self.om
        with om.runtime.experiment('test') as exp:
            exp.log_system()
        data = exp.data(key='system')
        system = data.iloc[0]['value']
        self.assertEqual(system['platform'], platform.uname()._asdict())
        self.assertEqual(system['platform']['node'], platform.node())

    def test_profiling(self):
        om = self.om
        with om.runtime.experiment('proftest', provider='profiling') as exp:
            exp.profiler.interval = 0.1
            sleep(1.5)
        data = exp.data(event='profile')
        self.assertGreaterEqual(len(data), 9)
        xexp = om.runtime.experiment('proftest')
        self.assertIsInstance(xexp.experiment, OmegaProfilingTracker)

    def test_track_then_notracking(self):
        # test experiments are stopped afterwards
        om = self.om
        # start an experiment
        with om.runtime.experiment('myexp') as exp:
            pass
        exp = om.models.get('experiments/myexp', data_store=om.datasets)
        # check that it is removed afterwards
        om.runtime.ping()
        self.assertEqual(len(exp.data(event='metric')), 0)
        self.assertEqual(len(exp.data()), 3)  # includes system, start, stop


if __name__ == '__main__':
    unittest.main()
