from unittest import TestCase, mock, skip

import numpy as np
import pandas as pd
from numpy import random
from omegaml.backends.monitoring.alerting import AlertRule
from omegaml.backends.monitoring.datadrift import DataDriftMonitor
from omegaml.backends.monitoring.modeldrift import ModelDriftMonitor
from omegaml.backends.monitoring.stats import DriftStats
from omegaml.backends.virtualobj import virtualobj
from omegaml.tests.util import OmegaTestMixin
from sklearn.linear_model import LinearRegression


class DriftMonitoringTests(OmegaTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.df = self.setup_testdata()
        random.seed(seed=42)  # ensure we always get the same sampling data

    def tearDown(self):
        pass

    def setup_testdata(self):
        from plotly import express as px
        om = self.om
        gapminder = px.data.gapminder()
        om.datasets.drop('gapminder', force=True)
        om.datasets.put(gapminder, 'gapminder')
        return gapminder

    def test_dataframe_drift(self):
        om = self.om
        with om.runtime.experiment('test') as exp:
            mon = DataDriftMonitor('foo', store=om.datasets, tracking=exp)
        df = pd.DataFrame({
            'x': np.random.uniform(0, 1, 100),
        })
        snapshot = mon.snapshot(df)
        self.assertIn('stats', snapshot)
        self.assertIn('info', snapshot)
        self.assertIn('num_columns', snapshot['info'])
        self.assertEqual(snapshot['info']['num_columns'], ['x'])
        self.assertEqual(snapshot['info']['cat_columns'], [])
        data = mon.data
        self.assertEqual(len(data), 1)
        drift = mon.drift(raw=True)
        self.assertIn('info', drift)
        self.assertIn('stats', drift)
        self.assertEqual(drift['info']['seq'], [0, 0])
        self.assertEqual(drift['result']['drift'], False)

    def test_model_drift_stats(self):
        om = self.om
        with om.runtime.experiment('test') as exp:
            for i in range(5):
                exp.log_metric('score', 1.0)
                exp.stop()
        mon = ModelDriftMonitor('test', store=om.datasets, tracking=exp)
        mon.snapshot(run=1)
        mon.snapshot(run=range(1, 5))
        print(mon.drift(seq='baseline').describe())

    def test_dataset_drift(self):
        om = self.om
        with om.runtime.experiment('test') as exp:
            mon = DataDriftMonitor('foo', store=om.datasets, tracking=exp)
            mon.clear(force=True)
        df = self.df
        # -- baseline
        mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', year__lte=1960)
        # -- see if we can find drift
        #    expected: drift in lifeExp, gdpPercap, pop
        mon.snapshot('gapminder',
                     year__gt=1985,
                     country__in=['Switzerland', 'Germany'])
        # check snapshots store expected data
        data = mon.data[-1]
        for col in 'lifeExp', 'gdpPercap', 'pop':
            self.assertIn(col, data['stats'])
        self.assertEqual(set(df.columns), set(data['info']['num_columns'] +
                                              data['info']['cat_columns']))
        # check we get a valid drift report
        report = mon.report(seq=[0, -1], format='dict')
        self.assertIn('info', report)
        self.assertIn('seq', report['info'])
        self.assertIn('stats', report)
        # check we have overall drift
        self.assertTrue(report['result']['drift'])
        self.assertIn('lifeExp', report['result']['columns'], )
        """
        example_report = {'info': {'ci': 0.95,
                                   'dt_from': '2024-02-23T14:50:51.413002',
                                   'dt_to': '2024-02-23T14:50:51.432458',
                                   'seq': [0, -1]},
                          'result': {'columns': ['lifeExp',
                                                 'iso_num',
                                                 'country',
                                                 'continent',
                                                 'iso_alpha'],
                                     'drift': True,
                                     'method': 'mean',
                                     'metric': 0.625},
                          'stats': {'continent': {'chisq': {'drift': True,
                                                            'location': None,
                                                            'metric': 3.7333333333333334,
                                                            'pvalue': 0.4432963583745305},
                                                  'mean': {'drift': True,
                                                           'metric': 1.0,
                                                           'stats': ['chisq']}},
                                    'country': {'chisq': {'drift': True,
                                                          'location': None,
                                                          'metric': 70.00000000000001,
                                                          'pvalue': 0.9999999128777957},
                                                'mean': {'drift': True,
                                                         'metric': 1.0,
                                                         'stats': ['chisq']}},
                                    'gdpPercap': {'ks': {'drift': False,
                                                         'location': 0,
                                                         'metric': 0.4,
                                                         'pvalue': 0.41752365281777043},
                                                  'mean': {'drift': False, 'metric': 0.0, 'stats': []}},
                                    'iso_alpha': {'chisq': {'drift': True,
                                                            'location': None,
                                                            'metric': 70.00000000000001,
                                                            'pvalue': 0.999999875338478},
                                                  'mean': {'drift': True,
                                                           'metric': 1.0,
                                                           'stats': ['chisq']}},
                                    'iso_num': {'ks': {'drift': True,
                                                       'location': 5,
                                                       'metric': 1.0,
                                                       'pvalue': 1.0825088224469026e-05},
                                                'mean': {'drift': True, 'metric': 1.0, 'stats': ['ks']}},
                                    'lifeExp': {'ks': {'drift': True,
                                                       'location': 2,
                                                       'metric': 1.0,
                                                       'pvalue': 1.0825088224469026e-05},
                                                'mean': {'drift': True, 'metric': 1.0, 'stats': ['ks']}},
                                    'pop': {'ks': {'drift': False,
                                                   'location': 0,
                                                   'metric': 0.5,
                                                   'pvalue': 0.16782134274394334},
                                            'mean': {'drift': False, 'metric': 0.0, 'stats': []}},
                                    'year': {'ks': {'drift': False,
                                                    'location': 0,
                                                    'metric': 0.3,
                                                    'pvalue': 0.7869297884777761},
                                             'mean': {'drift': False, 'metric': 0.0, 'stats': []}}}}
            """

    def test_many_snapshots(self):
        # test for stability of drift calculations
        # -- since snapshots are histograms, thus imprecise, we need to test for stability
        # -- we do this by running the same sequence of snapshots multiple times
        for i in range(100):
            self.setUp()
            self.test_datadrift_sequence()
            self.test_datadrift_vs_baseline()

    def test_datadrift_sequence(self):
        om = self.om
        with om.runtime.experiment('test') as exp:
            mon = DataDriftMonitor('foo', store=om.datasets, tracking=exp)
            mon.clear(force=True)
        df = self.df
        # -- baseline
        mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', year__lte=1960)
        # -- a number of snapshots
        mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', year__gt=1960, year__lte=1970)
        mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', year__gt=1970, year__lte=1980)
        mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', year__gt=1980)
        # -- get all drifts since baseline
        drifts = mon.drift(seq=True, raw=True)
        # expect 3 drift calculations
        self.assertEqual(len(drifts), 3)
        # -- 1960/1970, 1970/1980, 1980/now
        self.assertEqual(drifts[0]['info']['seq'], [0, 1])
        self.assertEqual(drifts[1]['info']['seq'], [1, 2])
        self.assertEqual(drifts[2]['info']['seq'], [2, 3])
        # -- expect some drifts
        self.assertTrue(any(d['result']['drift'] for d in drifts))

    def test_datadrift_vs_baseline(self):
        om = self.om
        with om.runtime.experiment('test') as exp:
            mon = DataDriftMonitor('foo', store=om.datasets, tracking=exp)
            mon.clear(force=True)
        df = self.df
        # -- baseline
        mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', year__lte=1960)
        # -- a number of snapshots
        mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', year__gt=1960, year__lte=1970)
        mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', year__gt=1970, year__lte=1980)
        mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', year__gt=1980)
        # -- get all drifts since baseline
        #    comparing each snapshot to the baseline
        drifts = mon.drift(seq='baseline', raw=True)
        # expect 3 drift calculations
        # -- note how this is different from test_datadrift_sequence
        self.assertEqual(len(drifts), 3)
        # -- 1960/1970, 1960/1980, 1960/now
        self.assertEqual(drifts[0]['info']['seq'], [0, 1])
        self.assertEqual(drifts[1]['info']['seq'], [0, 2])
        self.assertEqual(drifts[2]['info']['seq'], [0, 3])
        # -- expect drifts in 1960/1970 and 1980/now
        self.assertEqual(drifts[0]['result']['drift'], True)
        self.assertEqual(drifts[1]['result']['drift'], True)
        self.assertEqual(drifts[2]['result']['drift'], True)
        # -- expect drifts in lifeExp (1960/1980) and gdpPercap (1980/now)
        self.assertIn('pop', drifts[0]['result']['columns'])
        self.assertIn('lifeExp', drifts[1]['result']['columns'])
        self.assertIn('lifeExp', drifts[2]['result']['columns'])

    def _setup_model(self, exp_name='test', model_name='test', save_xy=False, autotrack=False):
        om = self.om
        with om.runtime.experiment(exp_name, autotrack=autotrack) as exp:
            exp.clear(force=True)
            for i in range(100):
                exp.start()
                if i == 0:
                    # baseline
                    X = np.array(np.random.random(size=(10, 4)))
                    y = np.dot(X, np.random.random(size=(4, 1))) + np.random.random()
                    lm = LinearRegression()
                    lm.fit(X, y)
                    om.models.put(lm, model_name)
                    if save_xy:
                        om.datasets.put(X, f'X_{i}')
                        om.datasets.put(y, f'Y_{i}')
                else:
                    # introduce concept drift by scaling the coefficients => drift in accuracy
                    X = np.array(np.random.random(size=(10, 4)) * 1000)
                    y = np.dot(X, np.random.random(size=(4, 1)) * 1000) + np.random.random() * 5
                    if save_xy:
                        om.datasets.put(X, f'X_{i}')
                        om.datasets.put(y, f'Y_{i}')
                exp.log_metric('acc', lm.score(X, y))
                exp.stop()

        return exp

    def test_model_drift(self):
        om = self.om
        exp = self._setup_model()
        mon = ModelDriftMonitor('foo', tracking=exp, store=om.datasets)
        # print(exp.data(run='all', event='metric')['run'].unique())
        # create several snapshots of the model stats (i.e. calculate baseline statistics)
        # -- we simulate taking arbitrary snapshots, every time snapshotting different run sequences
        # -- run #1 does not have any snapshots, hence exclude it
        for runs in [range(2, 3), range(2, 50), range(50, 70), range(70, 100)]:
            snapshot = mon.snapshot(run=runs)
            self.assertIsInstance(snapshot, dict)
            self.assertEqual(snapshot['info']['run'], list(runs))
        # THINK: when the monitor is based on tracking, we should be able to specify
        # a sequence of runs directly, instead of snapshots
        # seq= should be named snapshots=, and alternative runs= (with tracking) to avoid confusion
        # perhaps not, as to ensure we always work on actually captured snapshots?
        drift = mon.drift(seq=[0] + list(range(-3, 0)), ci=.9, raw=True)
        # -- expect 3 drift calculations
        self.assertEqual(len(drift), 3)
        self.assertEqual(drift[0]['info']['seq'], [0, 1])
        self.assertEqual(drift[1]['info']['seq'], [1, 2])
        self.assertEqual(drift[2]['info']['seq'], [2, 3])
        # -- expect some drift from baseline to 2/3, 50/70, 70/100
        self.assertTrue(any(d['result']['drift'] for d in drift))

    def test_model_drift_xy(self):
        om = self.om
        exp = self._setup_model(save_xy=True)
        mon = ModelDriftMonitor('foo', tracking=exp, store=om.datasets)
        mon.snapshot(run=1)
        mon.snapshot(run=range(3, 50))
        mon.snapshot(run=range(50, 70))
        mon.snapshot(run=range(70, 100))
        mon.snapshot(X='X_0', Y='Y_0')
        mon.snapshot(X='X_99', Y='Y_99')
        drift = mon.drift()
        self.assertTrue(drift.drifted('X_0'))
        self.assertTrue(drift.drifted('Y_0'))
        plot = drift.plot('acc', 'ks')
        drift.describe()

    def test_model_drift_autotrack(self):
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
            om.runtime.model('regmodel').fit('sample[x]', 'sample[y]').get()
            om.runtime.model('regmodel').predict('sample[x]').get()
        mon = exp.as_monitor('regmodel')
        mon.snapshot(event='fit')
        mon.snapshot(event='predict')
        # expect 2 snapshots
        # -- fit: X, Y
        # -- predict: X, Y
        self.assertEqual(len(mon.data), 2)
        mon.drift(matcher={'Y_y': 'Y_0'})

    def test_capture_event(self):
        om = self.om
        exp = self._setup_model(save_xy=True)
        mon = ModelDriftMonitor('foo', tracking=exp, store=om.datasets)
        mon.snapshot(X='X_0', Y='Y_0')
        mon.snapshot(X='X_99', Y='Y_99')
        # capture overall model drift
        captured = mon.capture()
        self.assertTrue(captured)
        events = exp.data(event='drift')
        self.assertEqual(events.iloc[0]['value'], {'feature': True, 'label': True, 'metrics': False, 'seqs': [[0, 1]]})
        self.assertEqual(events.iloc[0]['seq'], [0, 1])
        self.assertEqual(events.iloc[0]['column'], '*')
        # capture specific feature drift
        captured = mon.capture(column='X_0')
        self.assertTrue(captured)
        events = exp.data(event='drift')
        self.assertEqual(events.iloc[-1]['value'], {'X_0': True, 'seqs': [[0, 1]]})
        self.assertEqual(events.iloc[-1]['seq'], [0, 1])
        self.assertEqual(events.iloc[-1]['column'], 'X_0')

    def test_alert_rule_notify(self):
        om = self.om
        exp = self._setup_model(save_xy=True)
        mon = ModelDriftMonitor('foo', tracking=exp, store=om.datasets)
        mon.snapshot(X='X_0', Y='Y_0')
        mon.snapshot(X='X_99', Y='Y_99')
        # capture overall model drift
        captured = mon.capture()
        stats = mon.captured(stats=True)
        self.assertTrue(stats.drifted())
        # check alert rule is called upon detected drift
        rule = AlertRule(monitor=mon, event='drift', action='notify', recipients=['me'])
        with mock.patch.object(rule, 'notify') as m_notify:
            rule.check()
            m_notify.assert_called_once()
        rule.check()

    def test_runtime_integration_modeldrift(self):
        om = self.om
        self._setup_model()
        # test creating a monitor from a runtime experiment
        with om.runtime.experiment('test', autotrack=True, recreate=True) as exp:
            exp.track('test', monitor=True)
        mon = exp.as_monitor('test', schedule='weekly')
        meta = om.models.metadata('test')
        self.assertIsInstance(mon, ModelDriftMonitor)
        self.assertIn('tracking', meta.attributes)
        self.assertIn('monitors', meta.attributes['tracking'])
        self.assertIn({'experiment': 'test', 'provider': 'models',
                       'alerts': [{'event': 'drift', 'recipients': []}],
                       'schedule': 'weekly'},
                      meta.attributes['tracking']['monitors'])
        # test getting the monitor does not add it again
        mon = exp.as_monitor('test', alerts=[{'event': 'drift', 'recipients': ['me']}])
        self.assertIsInstance(mon, ModelDriftMonitor)
        meta = om.models.metadata('test')
        self.assertIn({'experiment': 'test', 'provider': 'models',
                       'alerts': [{'event': 'drift', 'recipients': ['me']}],
                       'schedule': 'weekly'},
                      meta.attributes['tracking']['monitors'])
        self.assertEqual(len(meta.attributes['tracking']['monitors']), 1)

    def test_modeldrift_alert(self):
        om = self.om
        self._setup_model()
        # test creating a monitor job from a runtime experiment
        # -- create the monitor
        with om.runtime.experiment('test', autotrack=True, recreate=True) as exp:
            exp.track('test', monitor=True)
            mon = exp.as_monitor('test')
        # -- add snapshots
        mon.snapshot(run=range(2, 3))
        mon.snapshot(run=range(3, 100))
        self.assertTrue(mon.drifted())
        meta = om.models.metadata('test')
        self.assertIsInstance(mon, ModelDriftMonitor)
        self.assertIn('tracking', meta.attributes)
        self.assertIn('monitors', meta.attributes['tracking'])
        self.assertIn({'experiment': 'test', 'provider': 'models',
                       'alerts': [{'event': 'drift', 'recipients': []}],
                       'schedule': 'daily'},
                      meta.attributes['tracking']['monitors'])
        # test getting the monitor does not add it again
        # -- get the monitor
        mon = exp.as_monitor('test')
        self.assertIsInstance(mon, ModelDriftMonitor)
        # -- ensure the monitor is not added again
        meta = om.models.metadata('test')
        self.assertIn({'experiment': 'test', 'provider': 'models',
                       'alerts': [{'event': 'drift', 'recipients': []}],
                       'schedule': 'daily'},
                      meta.attributes['tracking']['monitors'])
        self.assertEqual(len(meta.attributes['tracking']['monitors']), 1)
        # ensure the monitor job is created, run it
        # -- in a real setup this is done by the scheduled celery task
        om.runtime.task('omegaml.backends.monitoring.tasks.ensure_monitors').run()
        self.assertIn('monitors/test/test.ipynb', om.jobs.list())
        om.runtime.job('monitors/test/test').run()
        # -- check the monitor ran and created an alert
        jobmeta = om.jobs.metadata('monitors/test/test')
        alerts = mon.alerts(raw=True)
        self.assertEqual(jobmeta.attributes['job_runs'][-1]['status'], 'OK')
        self.assertEqual(len(alerts), 1)
        # check the alert is as expected
        # -- remove runtime dependent keys
        # -- note that the alert's value is a list of drifts
        drifts = alerts[0]['value']
        for k in 'userid', 'dt', 'node', 'run', 'step':
            del drifts[0][k]
        self.assertDictEqual({'column': '*',
                              'event': 'drift',
                              'experiment': 'test',
                              'key': 'test',
                              'monitor': 'test',
                              'seq': [0, 2],
                              'value': {'metrics': True, 'seqs': [[0, 1], [0, 2]]}}, drifts[0])

        # check can get back drift stats from alerts
        drifts = mon.alerts(stats=True)
        self.assertIsInstance(drifts, DriftStats)
        self.assertTrue(drifts.drifted())

    def test_model_autotrack_realistic(self):
        om = self.om
        reg = LinearRegression()
        om.models.put(reg, 'regmodel')
        df = pd.DataFrame({
            'x': range(1, 10)
        })
        df['y'] = df['x'] * 5 + 3
        om.datasets.put(df, 'sample', append=False)
        with om.runtime.experiment('foo', autotrack=True) as exp:
            exp.clear(force=True)
            exp.track('regmodel', monitor=True)
            mon = exp.as_monitor('regmodel')
            om.runtime.model('regmodel').fit('sample[x]', 'sample[y]').get()
            om.runtime.model('regmodel').score('sample[x]', 'sample[y]').get()
            mon.snapshot(run=-1)
            om.runtime.model('regmodel').predict('sample[x]').get()
            exp.log_data('XX', df)
            mon.snapshot(run=-1)
            mon.drift(seq='baseline').describe()

    def test_model_autotrack_california(self):
        from sklearn.datasets import fetch_california_housing
        om = self.om

        data = fetch_california_housing(as_frame=True)
        df_house = data.data
        df_house['y'] = data.target
        features = list(set(df_house.columns) - set('y'))

        with om.runtime.experiment('test', autotrack=True) as exp:
            mon = exp.as_monitor('experiments/test')
            mon.clear(force=True)

            train = df_house.sample(n=5000, replace=False)
            mon.snapshot(X=train[features],
                         Y=train[['y']])

            future = df_house.sample(n=5000, replace=False)
            future['y'] = future['y']

            mon.snapshot(X=future[features],
                         Y=future[['y']])

        future = df_house.sample(n=5000, replace=False)
        future['y'] = future['y'] * np.random.normal(1.5, 0, len(future))

        from sklearn.linear_model import LinearRegression
        train = df_house.sample(n=5000, replace=False)
        reg = LinearRegression()
        reg.fit(train[features], train['y'])
        reg.score(train[features], train['y'])
        om.models.put(reg, 'housing')

        with om.runtime.experiment('housing', autotrack=True, recreate=True) as exp:
            exp.clear(force=True)
            exp.track('housing', monitor=True)

            mon = exp.as_monitor('housing')
            mon.snapshot(X=train[features],
                         Y=train[['y']])

        data = future[features]
        om.runtime.model('housing').predict(data).get()
        mon.tracking.data(run='*')

        mon.snapshot()
        mon.capture()
        compared = mon.compare()
        compared.plot()

    @skip('autotracking for virtualobj models is not yet implemented, pending virtualobj.model support')
    def test_autotracking_virtualobj(self):
        om = self.om

        @virtualobj
        def mymodel(*args, **kwargs):
            return [42]

        om.models.put(mymodel, 'mymodel')
        df = pd.DataFrame({
            'x': range(1, 10)
        })
        df['y'] = df['x'] * 5 + 3
        om.datasets.put(df, 'sample', append=False)
        with om.runtime.experiment('foo', autotrack=True) as exp:
            exp.clear(force=True)
            exp.track('mymodel', monitor=True)
            mon = exp.as_monitor('mymodel')
            om.runtime.model('mymodel').fit('sample[x]', 'sample[y]').get()
            om.runtime.model('mymodel').score('sample[x]', 'sample[y]').get()
            mon.snapshot(run=-1)
            om.runtime.model('mymodel').predict('sample[x]').get()
            exp.log_data('XX', df)
            mon.snapshot(run=-1)
            mon.drift(seq='baseline').describe()

    def test_explicit_xy_model_tracking(self):
        import omegaml as om
        # create a model
        reg = LinearRegression()
        om.models.put(reg, 'mymodel')
        # create a dataset
        df = pd.DataFrame({
            'x': range(10)
        })
        df['y'] = df['x'] * 2 + 3
        om.datasets.put(df, 'sample')
        # autotrack model
        exp = om.runtime.experiment('myexp', autotrack=True, recreate=True)
        exp.track('mymodel', monitor=True)
        exp.clear(force=True)
        mon = exp.as_monitor('mymodel')
        # explicitely track a dataset
        snapshot = mon.snapshot(X=df['x'], Y=df['y'])
        self.assertIn('X', snapshot)
        self.assertIn('Y', snapshot)
        self.assertIsNotNone(snapshot['X'])
        self.assertIsNotNone(snapshot['Y'])
