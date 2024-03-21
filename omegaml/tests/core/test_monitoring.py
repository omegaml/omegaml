from unittest import TestCase, mock

import numpy as np
import pandas as pd
from pprint import pprint
from sklearn.linear_model import LinearRegression

from omegaml.backends.monitoring.alerting import AlertRule
from omegaml.backends.monitoring.datadrift import DataDriftMonitor
from omegaml.backends.monitoring.modeldrift import ModelDriftMonitor
from omegaml.backends.monitoring.stats import DriftStats
from omegaml.tests.util import OmegaTestMixin


class DriftMonitoringTests(OmegaTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.df = self.setup_testdata()

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

    def test_dataset_drift(self):
        om = self.om
        with om.runtime.experiment('test') as exp:
            mon = DataDriftMonitor('foo', store=om.datasets, tracking=exp)
            mon.clear()
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

    def test_datadrift_sequence(self):
        om = self.om
        with om.runtime.experiment('test') as exp:
            mon = DataDriftMonitor('foo', store=om.datasets, tracking=exp)
            mon.clear()
        df = self.df
        # -- baseline
        mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', year__lte=1960)
        # -- a number of snapshots
        mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', year__lte=1970)
        mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', year__lte=1980)
        mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', year__gt=1980)
        # -- get all drifts since baseline
        drifts = mon.drift(seq=True, raw=True)
        # expect 3 drift calculations
        self.assertEqual(len(drifts), 3)
        # -- 1960/1970, 1970/1980, 1980/now
        self.assertEqual(drifts[0]['info']['seq'], [0, 1])
        self.assertEqual(drifts[1]['info']['seq'], [1, 2])
        self.assertEqual(drifts[2]['info']['seq'], [2, 3])
        # -- expect drifts in 1960/1970 and 1980/now
        self.assertEqual(drifts[0]['result']['drift'], True)
        self.assertEqual(drifts[1]['result']['drift'], True)
        self.assertEqual(drifts[2]['result']['drift'], True)
        # -- expect drifts in lifeExp (1960/1980) and gdpPercap (1980/now)
        self.assertEqual(drifts[0]['result']['columns'], ['lifeExp'])
        self.assertEqual(drifts[1]['result']['columns'], ['lifeExp'])
        self.assertEqual(drifts[2]['result']['columns'], ['lifeExp', 'pop', 'gdpPercap'])

    def test_datadrift_vs_baseline(self):
        om = self.om
        with om.runtime.experiment('test') as exp:
            mon = DataDriftMonitor('foo', store=om.datasets, tracking=exp)
            mon.clear()
        df = self.df
        # -- baseline
        mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', year__lte=1960)
        # -- a number of snapshots
        mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', year__lte=1970)
        mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', year__lte=1980)
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
        self.assertEqual(drifts[0]['result']['columns'], ['lifeExp'])
        self.assertEqual(drifts[1]['result']['columns'], ['lifeExp', 'gdpPercap'])
        self.assertEqual(drifts[2]['result']['columns'], ['lifeExp', 'pop', 'gdpPercap'])

    def _setup_model(self, exp_name='test', model_name='test', save_xy=False):
        om = self.om
        with om.runtime.experiment(exp_name) as exp:
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
        print(exp.data(run='all', event='metric')['run'].unique())
        # create several snapshots of the model stats (i.e. calculate baseline statistics)
        # -- we simulate taking arbitrary snapshots, every time snapshotting different run sequences
        # -- run #1 does not have any snapshots, hence exclude it
        for runs in [range(2, 3), range(2, 50), range(50, 70), range(70, 100)]:
            snapshot = mon.snapshot(run=runs)
            self.assertIsInstance(snapshot, dict)
            self.assertEqual(snapshot['info']['run'], list(runs))
        # THINK: when the monitor is based on tracking, we should be able to specify
        # a sequnce of runs directly, instead of snapshots
        # seq= should be named snapshots=, and alternative runs= (with tracking) to avoid confusion
        # perhaps not, as to ensure we always work on actually captured snapshots?
        drift = mon.drift(seq=[0] + list(range(-3, 0)), ci=.9, raw=True)
        # -- expect 3 drift calculations
        self.assertEqual(len(drift), 3)
        self.assertEqual(drift[0]['info']['seq'], [0, 1])
        self.assertEqual(drift[1]['info']['seq'], [1, 2])
        self.assertEqual(drift[2]['info']['seq'], [2, 3])
        # -- expect a drift from baseline (run 2) to runs 3-50 (see _setup_model() for details)
        self.assertEqual(drift[0]['result']['drift'], True)
        # -- expect no drift from runs 3-50 to runs 50-70
        self.assertEqual(drift[1]['result']['drift'], False)
        # -- expect no drift from runs 50-70 to runs 70-100
        self.assertEqual(drift[2]['result']['drift'], False)
        pprint(drift)

    def test_model_drift_xy(self):
        om = self.om
        exp = self._setup_model(save_xy=True)
        mon = ModelDriftMonitor('foo', tracking=exp, store=om.datasets)
        mon.snapshot(X='X_0', Y='Y_0')
        mon.snapshot(X='X_99', Y='Y_99')
        drift = mon.drift()
        self.assertTrue(drift.drifted('X_0'))
        self.assertTrue(drift.drifted('Y_0'))

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
        self.assertEqual(events.iloc[0]['value'], {'feature': True, 'label': True, 'model': False})
        self.assertEqual(events.iloc[0]['seq'], [0, 1])
        self.assertEqual(events.iloc[0]['column'], '*')
        # capture specific feature drift
        captured = mon.capture(column='X_0')
        self.assertTrue(captured)
        events = exp.data(event='drift')
        self.assertEqual(events.iloc[-1]['value'], {'X_0': True})
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
        with om.runtime.experiment('test') as exp:
            exp.track('test', monitor=True)
        meta = om.models.metadata('test')
        mon = exp.as_monitor('test')
        self.assertIsInstance(mon, ModelDriftMonitor)
        self.assertIn('tracking', meta.attributes)
        self.assertIn('monitors', meta.attributes['tracking'])
        self.assertIn({'experiment': 'test', 'provider': 'models'},
                      meta.attributes['tracking']['monitors'])
        # test getting the monitor does not add it again
        mon = exp.as_monitor('test')
        self.assertIsInstance(mon, ModelDriftMonitor)
        meta = om.models.metadata('test')
        self.assertIn({'experiment': 'test', 'provider': 'models'},
                      meta.attributes['tracking']['monitors'])
        self.assertEqual(len(meta.attributes['tracking']['monitors']), 1)

    def test_modeldrift_alert(self):
        om = self.om
        self._setup_model()
        # test creating a monitor job from a runtime experiment
        # -- create the monitor
        with om.runtime.experiment('test') as exp:
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
        self.assertIn({'experiment': 'test', 'provider': 'models'},
                      meta.attributes['tracking']['monitors'])
        # test getting the monitor does not add it again
        # -- get the monitor
        mon = exp.as_monitor('test')
        self.assertIsInstance(mon, ModelDriftMonitor)
        # -- ensure the monitor is not added again
        meta = om.models.metadata('test')
        self.assertIn({'experiment': 'test', 'provider': 'models'},
                      meta.attributes['tracking']['monitors'])
        self.assertEqual(len(meta.attributes['tracking']['monitors']), 1)
        # -- ensure the monitor job is created, run it
        # -- in a real setup this is done by the scheduled celery task
        om.runtime.task('omegaml.backends.monitoring.tasks.ensure_monitors').run()
        self.assertIn('monitors/test/test', om.jobs.list())
        om.runtime.job('monitors/test/test').run()
        # -- check the monitor ran and created an alert
        jobmeta = om.jobs.metadata('monitors/test/test')
        alerts = mon.alerts(raw=True)
        self.assertEqual(jobmeta.attributes['job_runs'][-1]['status'], 'OK')
        self.assertEqual(len(alerts), 1)
        # -- check the alert is as expected
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
                              'value': {'model': True, 'seqs': [[0, 1], [0, 2]]}}, drifts[0])

        # -- check can get back drift stats from alerts
        drifts = mon.alerts(stats=True)
        self.assertIsInstance(drifts, DriftStats)
        self.assertTrue(drifts.drifted())
        # configure
        import omegaml as om
        experiment = 'test'
        name = 'test'
        provider = 'models'
        alerts = [{'event': 'drift', 'recipients': []}]
        # snapshot recent state and capture drift
        with om.runtime.experiment(experiment) as exp:
            mon = exp.as_monitor(name, store=om.models, provider=provider)
            mon.snapshot()
            mon.capture(alerts=alerts)
