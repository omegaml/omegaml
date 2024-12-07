import datetime
import pandas as pd
import platform
import pymongo
import unittest
from numpy.testing import assert_almost_equal
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression, LinearRegression
from time import sleep

from omegaml import Omega
from omegaml.backends.tracking.experiment import ExperimentBackend
from omegaml.backends.tracking.profiling import OmegaProfilingTracker
from omegaml.backends.tracking.simple import OmegaSimpleTracker, dtrelative
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
        self.assertTrue(any(set(keys) & {'data.event', 'data.key', 'data.run'} for keys in idxs_keys))
        self.assertTrue(any(set(keys) & {'data.event', 'data.key', 'data.dt'} for keys in idxs_keys))

    def test_clear(self):
        om = self.om
        exp = om.runtime.experiment('test')
        with exp:
            exp.log_metric('accuracy', .98)
        self.assertEqual(len(exp.data()), 3)
        exp.clear(force=True)
        self.assertIsNone(exp.data())

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
        tracker = om.runtime.experiment('expfoo', autotrack=True)
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
        # get back data
        data = exp.data(event='predict', key=['X', 'Y'], run='*')
        self.assertEqual(len(data), 2)  # 2x X, Y
        # check we get back autotracked X, Y
        # -- X is the same as given to fit/predict
        # -- Y/score: technically we expect 1.0, give some slack
        tracked_X = exp.restore_data(event='predict', key='X', run='*')
        tracked_Y = exp.restore_data(event='predict', key='Y', run='*')
        assert_almost_equal(tracked_X, X)
        self.assertTrue(lr.score(X, tracked_Y) > 0.9)
        # note if we run the same prediction again, we get two runs
        # -- thus double the amount of data for X, Y respectively
        om.runtime.model('mymodel').predict(X)
        tracked_X = exp.restore_data(event='predict', key='X', run='*')
        tracked_Y = exp.restore_data(event='predict', key='Y', run='*')
        self.assertEqual(len(tracked_X), 2 * len(X))
        self.assertEqual(len(tracked_Y), 2 * len(Y))
        # -- we can also get back each run's data
        for i_run in (-1, -2):
            tracked_X = exp.restore_data(event='predict', key='X', run=i_run)
            tracked_Y = exp.restore_data(event='predict', key='Y', run=i_run)
            self.assertEqual(len(tracked_X), len(X))
            self.assertEqual(len(tracked_Y), len(Y))

    def test_tracking_runtime_taskid(self):
        # create a model
        om = self.om
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression(solver='liblinear', multi_class='auto')
        lr.fit(X, Y)
        om.models.put(lr, 'mymodel')
        tracker = om.runtime.experiment('expfoo', autotrack=True)
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
        self.assertIsInstance(exps['_all_'][0], OmegaTrackingProxy)
        self.assertIsInstance(exps['default'], OmegaTrackingProxy)
        # get metadata of experiments, instead of tracking proxies
        exps = rtmdl.experiments(raw=True)
        self.assertIsInstance(exps['_all_'][0], om.models._Metadata)
        self.assertIsInstance(exps['default'], om.models._Metadata)

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

    def test_lazy_data(self):
        om = self.om
        for i in range(10):
            with om.runtime.experiment('myexp') as exp:
                exp.log_metric('accuracy', i)
            exp.flush()
        data = exp.data(lazy=True)
        self.assertIsInstance(data, pymongo.cursor.Cursor)

    def test_raw_data(self):
        om = self.om
        for i in range(10):
            with om.runtime.experiment('myexp') as exp:
                exp.log_metric('accuracy', i)
            exp.flush()
        data = exp.data(run='all', raw=True)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 10 * 3)  # each run has 3 events

    def test_batched_data(self):
        om = self.om
        for i in range(10):
            with om.runtime.experiment('myexp') as exp:
                exp.log_metric('accuracy', i)
            exp.flush()
        # raw=True yields DataFrames, raw=False yields lists of rows
        for raw, result_type in zip((True, False), (list, pd.DataFrame)):
            data = exp.data(run='all', batchsize=5, raw=raw)
            total_rows = sum(len(rows) for rows in data if isinstance(rows, result_type))
            self.assertEqual(total_rows, 10 * 3)  # each run has 3 events

    def test_data_slice(self):
        om = self.om
        for i in range(10):
            with om.runtime.experiment('myexp') as exp:
                exp.log_metric('accuracy', i)
            exp.flush()
        # slice on records
        data = exp.data(run='*', slice=slice(0, 5))
        self.assertEqual(len(data), 5)
        data = exp.data(run='*', slice=(3, 3 + 2))
        self.assertEqual(len(data), 2)
        # slice on runs
        data = exp.data(run=slice(0, 5))
        self.assertEqual(len(data), 5 * 3)  # every run has 3 events (start, metric, stop)

    def test_current_vs_all_data(self):
        om = self.om
        for i in range(10):
            with om.runtime.experiment('myexp') as exp:
                exp.log_metric('accuracy', i)
            exp.flush()
        data = exp.data()
        # only current run
        self.assertEqual(len(data), 3)
        # all runs
        data = exp.data(run='*')
        self.assertEqual(len(data), 10 * 3)  # each run has 3 events

    def test_model_autotrack(self):
        om = self.om
        df = pd.DataFrame({
            'x': range(1, 10)
        })
        df['y'] = df['x'] * 5 + 3
        reg = LinearRegression()
        om.models.put(reg, 'regmodel')
        om.datasets.put(df, 'sample')
        # set up monitoring
        with om.runtime.experiment('myexp', autotrack=True) as exp:
            exp.track('regmodel', monitor=True)
        # check the monitor is automatically active
        om.runtime.model('regmodel').fit('sample[x]', 'sample[y]').get()
        om.runtime.model('regmodel').predict('sample[x]').get()
        # check fit and predict were tracked
        data = exp.data(run='*', event='fit', key=['X', 'Y'])
        self.assertEqual(len(data), 2)
        data = exp.data(run='*', event='predict', key=['X', 'Y'])
        self.assertEqual(len(data), 2)

    def test_run_monotonically_increased(self):
        om = self.om
        for i in range(1, 10):
            with om.runtime.experiment('myexp') as exp:
                exp.log_metric('acc', 0)
            self.assertEqual(exp._latest_run, i)
        data = exp.data(run='*')
        self.assertEqual(list(data['run'].unique()), list(range(1, 10)))
        data = exp.data(run=1)
        self.assertEqual(data['run'].unique(), [1])

    def test_since_filter(self):
        om = self.om
        dt_start = dt = datetime.datetime.utcnow()
        for i in range(0, 10):
            with om.runtime.experiment('myexp') as exp:
                exp.log_metric('acc', 0, dt=dt)
                dt = dt + datetime.timedelta(hours=1)
        # all data since start
        data = exp.data(event='metric', key='acc', since=dt_start)
        self.assertEqual(len(data), 10)
        # only last 5 hours
        data = exp.data(event='metric', key='acc', since=dt_start + datetime.timedelta(hours=5))
        self.assertEqual(len(data), 5)
        # only last hour
        data = exp.data(event='metric', key='acc', since=dt_start + datetime.timedelta(hours=9))
        self.assertEqual(len(data), 1)
        # all data since start - 1 hour
        data = exp.data(event='metric', key='acc', since=dt_start - datetime.timedelta(hours=1))
        self.assertEqual(len(data), 10)
        # make sure run=1 is not ignored when since is set
        data = exp.data(run=1, event='metric', key='acc')
        self.assertEqual(len(data), 1)
        data = exp.data(run=1, event='metric', key='acc', since=dt_start + datetime.timedelta(hours=5))
        self.assertEqual(len(data), 0)
        data = exp.data(run=None, event='metric', key='acc', since=dt_start + datetime.timedelta(hours=5))
        self.assertEqual(len(data), 5)

    def test_since_delta_filter(self):
        om = self.om
        dt_start = dt = datetime.datetime.utcnow()
        for i in range(0, 10):
            with om.runtime.experiment('myexp') as exp:
                exp.log_metric('acc', 0, dt=dt)
                dt = dt + datetime.timedelta(hours=1)
        exp.experiment._since_dtnow = dt
        # all data since start
        data = exp.data(event='metric', key='acc', since='10h')
        self.assertEqual(len(data), 10)
        # only last 5 hours
        data = exp.data(event='metric', key='acc', since='5h')
        self.assertEqual(len(data), 5)
        # only last hour
        data = exp.data(event='metric', key='acc', since='1h')
        self.assertEqual(len(data), 1)
        # all data since start - 1 hour
        data = exp.data(event='metric', key='acc', since='-11h')
        self.assertEqual(len(data), 10)
        # make sure run=1 is not ignored when since is set
        data = exp.data(run=1, event='metric', key='acc')
        self.assertEqual(len(data), 1)
        data = exp.data(run=1, event='metric', key='acc', since='11h')
        self.assertEqual(len(data), 1)
        data = exp.data(run=1, event='metric', key='acc', since='5h')
        self.assertEqual(len(data), 0)

    def test_dtrelative(self):
        from datetime import datetime, timedelta
        # Define a fixed 'now' for testing purposes
        now = datetime(2024, 10, 16, 12, 0, 0)  # Oct 16, 2024, 12:00:00
        # Test cases for each unit with positive and negative deltas
        assert dtrelative("0h", now) == now
        assert dtrelative("10s", now) == now + timedelta(seconds=10)  # Seconds
        assert dtrelative("-10s", now) == now - timedelta(seconds=10)
        assert dtrelative("5m", now) == now + timedelta(minutes=5)  # Minutes
        assert dtrelative("-5m", now) == now - timedelta(minutes=5)
        assert dtrelative("2h", now) == now + timedelta(hours=2)  # Hours
        assert dtrelative("-2h", now) == now - timedelta(hours=2)
        assert dtrelative("1d", now) == now + timedelta(days=1)  # Days
        assert dtrelative("-1d", now) == now - timedelta(days=1)
        assert dtrelative("1w", now) == now + timedelta(weeks=1)  # Weeks
        assert dtrelative("-1w", now) == now - timedelta(weeks=1)
        assert dtrelative("1n", now) == now + timedelta(days=30)  # Months (~30 days)
        assert dtrelative("-1n", now) == now - timedelta(days=30)
        assert dtrelative("1q", now) == now + timedelta(days=90)  # Quarters (~90 days)
        assert dtrelative("-1q", now) == now - timedelta(days=90)
        assert dtrelative("1y", now) == now + timedelta(days=365)  # Years (~365 days)
        assert dtrelative("-1y", now) == now - timedelta(days=365)
        assert dtrelative("0y", now) == datetime(now.year, 12, 31)  # Year end
        assert dtrelative("-0y", now) == datetime(now.year, 1, 1)  # Year start
        # Test case for timedelta input
        assert dtrelative(timedelta(days=2), now) == now + timedelta(days=2)
        with self.assertRaises(ValueError):
            dtrelative("invalid", now)
        with self.assertRaises(ValueError):
            dtrelative("10x", now)

    def test_daterange_filter(self):
        om = self.om
        dt_start = dt = datetime.datetime.utcnow()
        for i in range(0, 10):
            with om.runtime.experiment('myexp') as exp:
                exp.log_metric('acc', 0, dt=dt)
                dt = dt + datetime.timedelta(hours=1)
        # try datetime range since start
        for i in range(0, 10):
            data = exp.data(event='metric', key='acc', since=dt_start, end=dt_start + datetime.timedelta(hours=i))
            self.assertEqual(len(data), i + 1)
        # try datetime for arbitrary ranges
        for delta_start, delta_end in [(1, 4), (2, 6)]:
            data = exp.data(event='metric', key='acc',
                            since=dt_start + datetime.timedelta(hours=delta_start),
                            end=dt_start + datetime.timedelta(hours=delta_end))
            self.assertEqual(len(data), delta_end - delta_start + 1, f'{delta_start} {delta_end}')

    def test_restore_xy_data(self):
        om = self.om
        exp: OmegaSimpleTracker
        with om.runtime.experiment('myexp') as exp:
            df = pd.DataFrame({'x': range(0, 10)})
            exp.log_data('Y', df['x'])
        with om.runtime.experiment('myexp') as exp:
            ds = pd.Series(range(0, 10)).values
            exp.log_data('Y', ds)
        dfx = exp.restore_data('Y', run='*')
        self.assertEqual(len(dfx), 20)


if __name__ == '__main__':
    unittest.main()
