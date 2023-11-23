from time import sleep

import platform

import pandas as pd
import unittest
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression

from omegaml import Omega
from omegaml.backends.tracking.simple import OmegaSimpleTracker
from omegaml.backends.tracking.profiling import OmegaProfilingTracker
from omegaml.backends.tracking.experiment import ExperimentBackend
from omegaml.documents import Metadata
from omegaml.runtimes.proxies.trackingproxy import OmegaTrackingProxy
from omegaml.tests.util import OmegaTestMixin


class TrackingTestCases(OmegaTestMixin, unittest.TestCase):
    def setUp(self):
        self.om = om = Omega()
        self.clean()
        om.models.register_backend(ExperimentBackend.KIND, ExperimentBackend)

    def test_initialize(self):
        om = self.om
        exp = om.runtime.experiment('test')
        coll = om.datasets.collection(exp._data_name)
        # SON(..., 'keys': { key: order, ...}) => ['key', ...]
        idxs = [son.to_dict()['key'] for son in coll.list_indexes()]
        idxs_keys = [list(sorted(d.keys())) for d in idxs]
        self.assertTrue(any(keys == ['data.event', 'data.run'] for keys in idxs_keys))

    def test_ensure_active(self):
        # explicit start
        om = self.om
        exp = om.runtime.experiment('test')
        with self.assertRaises(ValueError):
            exp.log_param('foo', 'bar')
        run = exp.start()
        exp.log_param('foo', 'bar')
        exp.flush()
        data = exp.data(run=run)
        self.assertIsNotNone(run)
        self.assertEqual(len(data), 2)
        # reuse latest run
        exp = om.runtime.experiment('test')
        with self.assertRaises(ValueError):
            exp.log_param('foo', 'bar')
        exp.use()
        exp.log_param('foo', 'bax')
        exp.stop()
        data = exp.data(run=run)
        self.assertIsNotNone(run)
        self.assertEqual(len(data), 4)
        # implied run should be NOT set in with block if use() was called previously
        # rationale: with exp should always start a new run
        with exp as xexp:
            xexp.log_param('foo', 'bar')
        data = xexp.data()
        self.assertEqual(len(data), 3)
        self.assertEqual(set(data['event']), {'start', 'stop', 'param'})
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
            # check exp is associated with correct stores
            self.assertEqual(exp._model_store, om.models)
            self.assertEqual(exp._store, om.datasets)
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
        self.assertEqual(len(data), 15)  # includes runtime task events
        self.assertEqual(len(data[data.event == 'start']), 2)
        self.assertEqual(len(data[data.event == 'stop']), 2)
        self.assertEqual(len(data[data.event == 'artifact']), 4)
        artifacts = data[data.event == 'artifact']['value'].to_list()
        with self.assertWarns(DeprecationWarning):
            obj = exp.restore_artifact(key='mymodel')
            self.assertIsInstance(obj, LogisticRegression)
        obj = exp.restore_artifacts(key='mymodel')
        self.assertIsInstance(obj[0], LogisticRegression)
        obj = exp.restore_artifacts(key='mymodel_meta')
        self.assertIsInstance(obj[0], Metadata)
        # related is stored by runtime automatically as the delegate's metadata
        obj = exp.restore_artifacts(key='related')
        self.assertIsInstance(obj[0], Metadata)
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

    def test_tracking_predictions_explicit_metadata(self):
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

    def test_tracking_predictions_implicit_tracker(self):
        # create a model
        om = self.om
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression(solver='liblinear', multi_class='auto')
        lr.fit(X, Y)
        om.models.put(lr, 'mymodel')
        tracker = om.runtime.experiment('expfoo')
        tracker.track('mymodel')
        om.runtime.model('mymodel').score(X, Y)
        exp = tracker.experiment
        data = exp.data()
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 6)
        # run a prediction to see if this is tracked
        om.runtime.model('mymodel').predict(X)
        tracker = om.runtime.experiment('expfoo')
        data = exp.data()
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 13)

    def test_tracking_runtime_taskid(self):
        # create a model
        om = self.om
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression(solver='liblinear', multi_class='auto')
        lr.fit(X, Y)
        om.models.put(lr, 'mymodel')
        tracker = om.runtime.experiment('expfoo')
        tracker.track('mymodel')
        resp = om.runtime.model('mymodel').score(X, Y)
        exp = tracker.experiment
        data = exp.data(taskid=resp.task_id)
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 6)
        self.assertEqual(data['run'].unique(), [1])
        resp = om.runtime.model('mymodel').score(X, Y)
        data = exp.data(taskid=resp.task_id)
        self.assertEqual(len(data), 6)
        self.assertEqual(data['run'].unique(), [2])
        # run a prediction to see if this is tracked
        om.runtime.model('mymodel').predict(X)
        tracker = om.runtime.experiment('expfoo')
        data = exp.data()
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 3 * 6 + 1)  # 3 runs, last one has X, Y entries

    def test_empty_experiment_data(self):
        om = self.om
        with om.runtime.experiment('myexp') as exp:
            pass
        exp = om.models.get('experiments/myexp', data_store=om.datasets)
        # we have at least a 'system' event
        self.assertEqual(len(exp.data(event='metric')), 0)
        self.assertEqual(len(exp.data()), 2)  # start, stop events

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
        data = exp.restore_artifacts('foo')
        self.assertIsInstance(data[0], dict)
        # by value
        data = exp.data(key='foo')
        data = exp.restore_artifacts(value=data.iloc[0].value)
        self.assertIsInstance(data[0], dict)

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
        self.assertEqual(len(exp.data()), 3)
        # check experiment and data where created
        self.assertIn('experiments/foo', om.models.list())
        meta = om.models.metadata('experiments/foo')
        dataset = meta.attributes['tracking']['dataset']
        self.assertIsNotNone(dataset)
        self.assertIn(dataset, om.datasets.list(hidden=True))
        self.assertIn('experiments/foo', om.models.list())
        # add a metric, then clean
        exp.log_metric(5, 'accuracy')
        exp.flush()
        self.assertEqual(len(exp.data()), 4)
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
        data = exp.data(event=['start', 'stop'])
        self.assertGreaterEqual(len(data), 2)
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
        self.assertEqual(len(exp.data()), 2)  # includes start, stop

    def test_runtime_experiments_links(self):
        # test experiments are stopped afterwards
        om = self.om
        # create a model and get its default experiment
        lr = LogisticRegression(solver='liblinear', multi_class='auto')
        om.models.put(lr, 'foo')
        # get default experiment, expect it to be tracking the model
        exp = om.runtime.model('foo').experiment()
        self.assertIsInstance(exp, OmegaTrackingProxy)
        meta = om.models.metadata('foo')
        self.assertIn('tracking', meta.attributes)
        self.assertEqual(meta.attributes['tracking']['default'], 'foo')
        # get the experiment again, this time it is not created again
        exp = om.runtime.model('foo').experiment()
        self.assertIsInstance(exp, OmegaTrackingProxy)
        self.assertEqual(exp.experiment._experiment, 'foo')
        # get the experiment by default runtime label
        rtmdl = om.runtime.model('foo')
        exp = rtmdl.experiment(label='default')
        self.assertIsInstance(exp, OmegaTrackingProxy)
        # get the experiment by arbitrary runtime label
        rtmdl = om.runtime.model('foo')
        exp = rtmdl.experiment(label='someotherlabel')
        meta = om.models.metadata('foo')
        self.assertIn('tracking', meta.attributes)
        self.assertEqual(meta.attributes['tracking']['someotherlabel'], 'foo')
        # get all experiments for the model, by default runtime label
        rtmdl = om.runtime.model('foo')
        exps = rtmdl.experiments()
        self.assertIsInstance(exps[0], OmegaTrackingProxy)
        # get metadata of experiments, instead of tracking proxies
        exps = rtmdl.experiments(raw=True)
        self.assertIsInstance(exps[0], om.models._Metadata)

    def test_summary(self):
        om = self.om
        for i in range(10):
            with om.runtime.experiment('myexp') as exp:
                exp.log_metric('accuracy', .98)
                exp.log_metric('mse', .02)
        summary = exp.summary()
        self.assertEqual(len(summary.loc['metric']), 3)
        self.assertEqual(set(summary.loc['metric'].index), {'accuracy', 'mse', 'latency'})
        summary = exp.summary(perf_stats=True)
        self.assertEqual(len(summary.loc['metric']), 5)
        self.assertEqual(set(summary.loc['metric'].index),
                         {'accuracy', 'mse', 'latency', 'utilization', 'group_latency'})

    def test_latency(self):
        om = self.om
        for i in range(10):
            with om.runtime.experiment('myexp') as exp:
                exp.log_metric('accuracy', .98)
        latency = exp.stats.latency(run='all', percentiles=False)
        self.assertEqual(len(latency), 10)
        latency_perc = exp.stats.latency(run='all', percentiles=True)
        self.assertEqual(len(latency_perc), 1)
        self.assertIn('50%', latency_perc.columns)


if __name__ == '__main__':
    unittest.main()
