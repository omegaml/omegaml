from unittest import TestCase, mock, skip

import datetime
import numpy as np
import pandas as pd
from numpy import random
from omegaml.backends.monitoring.alerting import AlertRule
from omegaml.backends.monitoring.datadrift import DataDriftMonitor
from omegaml.backends.monitoring.modeldrift import ModelDriftMonitor
from omegaml.backends.monitoring.stats import DriftStats, DriftStatsSeries, DriftStatsCalc
from omegaml.backends.virtualobj import virtualobj
from omegaml.tests.util import OmegaTestMixin, dict_almost_equal
from pandas._testing import assert_frame_equal
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder


class DriftMonitoringTests(OmegaTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.df = self.setup_testdata()
        random.seed(seed=42)  # ensure we always get the same sampling data
        # enable interactive plot output
        # mpl.use('TkAgg')

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
        drift = mon.compare(raw=True)
        drift = drift[0]
        self.assertIn('info', drift)
        self.assertIn('stats', drift)
        self.assertEqual(drift['info']['seq'], [-1, 0])
        self.assertEqual(drift['result']['drift'], False)

    def test_driftstats_mixin(self):
        om = self.om

        class MyDriftStatsCalc(DriftStatsCalc):
            def _init_mixin(self):
                self._metrics['numeric'].update({
                    'len': self.calc_len
                })

            def calc_len(self, d1, d2, **kwargs):
                metric = (len(d1) - len(d2)) / sum([len(d1), len(d2)])
                return {
                    'metric': metric,
                    'score': metric,
                    'drift': metric > 0.1,
                    'location': 0,
                    'pvalue': 0,
                }

        with om.runtime.experiment('test') as exp:
            mon = DataDriftMonitor('foo', store=om.datasets, tracking=exp)
            mon.statscalc._apply_mixins([MyDriftStatsCalc])

        df = pd.DataFrame({
            'x': np.random.uniform(0, 1, 100),
        })
        stats = mon.compare(d1=df, d2=df)
        self.assertIn('len', stats.data[0]['stats']['x'])

    def test_dataframe_drift_groupby(self):
        om = self.om
        with om.runtime.experiment('test') as exp:
            mon = DataDriftMonitor('foo', store=om.datasets, tracking=exp)
        mon = DataDriftMonitor(tracking=exp, store=om.datasets)
        mon.snapshot(dataset='gapminder[year,country,gdpPercap]',
                     filter=dict(country__in=['Switzerland', 'Germany'],
                                 year__lte=1960),
                     groupby=['country', 'year'])
        mon.snapshot(dataset='gapminder[year,country,gdpPercap]',
                     filter=dict(country__in=['Switzerland', 'Germany'],
                                 year__gte=1980),
                     groupby=['country', 'year'])
        stats = mon.compare()
        self.assertDictEqual(stats.summary(raw=True)['columns'],
                             {'country': False,
                              'country_Germany:1952': False,
                              'country_Germany:1957': False,
                              'country_Switzerland:1952': False,
                              'country_Switzerland:1957': False,
                              'gdpPercap': True,
                              'gdpPercap_Germany:1952': True,
                              'gdpPercap_Germany:1957': True,
                              'gdpPercap_Switzerland:1952': True,
                              'gdpPercap_Switzerland:1957': True,
                              'year': True,
                              'year_Germany:1952': True,
                              'year_Germany:1957': True,
                              'year_Switzerland:1952': True,
                              'year_Switzerland:1957': True})

    def test_model_drift_stats(self):
        om = self.om
        with om.runtime.experiment('test') as exp:
            for i in range(5):
                exp.log_metric('score', 1.0)
                exp.stop()
        mon = ModelDriftMonitor('test', store=om.datasets, tracking=exp)
        mon.snapshot(run=1)
        mon.snapshot(run=range(1, 5))
        summary = mon.compare(seq='baseline').describe().reset_index()
        self.assertEqual(set(summary['statistic'].values), {'ks', 'mean', 'wasserstein', 'jsd', 'kld'})

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
        drifts = mon.compare(seq='series', raw=True)
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
        mon.samples = [1000, 10000]
        drifts = mon.compare(seq='baseline', raw=True)
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
        self.assertTrue(any('pop' in drifts[i]['result']['columns'] for i in range(len(drifts))))
        self.assertTrue(any('lifeExp' in drifts[i]['result']['columns'] for i in range(len(drifts))))

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
        drift = mon.compare(seq=[0] + list(range(-3, 0)), ci=.9, raw=True)
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
        drift = mon.compare()
        self.assertTrue(drift.summary('X_0', raw=True)['columns']['X_0'])
        self.assertTrue(drift.summary('Y_0', raw=True)['columns']['Y_0'])
        plot = drift.plot('acc', 'ks')
        drift.describe()

    def test_model_drift_xy_groupby(self):
        om = self.om
        preprocessor = ColumnTransformer(
            transformers=[
                ('num', Pipeline([
                    ('scaler', StandardScaler()),
                ]), ['gdpPercap', 'pop', 'year']),  # Numerical features
                ('cat', OneHotEncoder(), ['county'])  # Categorical feature
            ]
        )

        # Create the pipeline
        pipeline = Pipeline([
            ('preprocessor', preprocessor),
            ('logreg', LogisticRegression())
        ])
        with om.runtime.experiment('test') as exp:
            mon = DataDriftMonitor('foo', store=om.datasets, tracking=exp)
        mon = DataDriftMonitor(tracking=exp, store=om.datasets)
        mon.snapshot(dataset='gapminder[year,country,gdpPercap]',
                     filter=dict(country__in=['Switzerland', 'Germany'],
                                 year__lte=1960),
                     groupby=['country', 'year'])
        mon.snapshot(dataset='gapminder[year,country,gdpPercap]',
                     filter=dict(country__in=['Switzerland', 'Germany'],
                                 year__gte=1980),
                     groupby=['country', 'year'])
        stats = mon.compare()
        self.assertDictEqual(stats.summary(raw=True)['columns'],
                             {'country': False,
                              'country_Germany:1952': False,
                              'country_Germany:1957': False,
                              'country_Switzerland:1952': False,
                              'country_Switzerland:1957': False,
                              'gdpPercap': True,
                              'gdpPercap_Germany:1952': True,
                              'gdpPercap_Germany:1957': True,
                              'gdpPercap_Switzerland:1952': True,
                              'gdpPercap_Switzerland:1957': True,
                              'year': True,
                              'year_Germany:1952': True,
                              'year_Germany:1957': True,
                              'year_Switzerland:1952': True,
                              'year_Switzerland:1957': True})

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
        mon.compare(matcher={'Y_y': 'Y_0'})

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
        self.assertTrue(dict_almost_equal(events.iloc[0]['value'],
                                          {'columns': {'X_0': True, 'X_1': True, 'X_2': True, 'X_3': True, 'Y_0': True,
                                                       'acc': False},
                                           'summary': {'feature': True, 'label': True, 'metrics': False},
                                           'info': {'feature': ['X_0', 'X_1', 'X_2', 'X_3'], 'label': ['Y_0'],
                                                    'metrics': ['acc'],
                                                    'seq': [[0, 1]]},
                                           'score': {'feature': 1.0, 'label': 1.0, 'metrics': 0.1}},
                                          tolerance=1e-1))
        # capture specific feature drift
        captured = mon.capture(column='X_0')
        self.assertTrue(captured)
        events = exp.data(event='drift')
        self.assertTrue(dict_almost_equal(events.iloc[-1]['value'],
                                          {'columns': {'X_0': True}, 'info': {'feature': ['X_0'], 'seq': [[0, 1]]},
                                           'summary': {'feature': True},
                                           'score': {'feature': 1.0}},
                                          tolerance=1e-1))

    def test_alert_rule_notify(self):
        om = self.om
        exp = self._setup_model(save_xy=True)
        mon = ModelDriftMonitor('foo', tracking=exp, store=om.datasets)
        mon.snapshot(X='X_0', Y='Y_0')
        mon.snapshot(X='X_99', Y='Y_99')
        # capture overall model drift
        captured = mon.capture()
        stats = mon.events(stats=True)
        self.assertTrue(dict_almost_equal(stats.summary(raw=True),
                                          {'columns': {'X_0': True, 'X_1': True, 'X_2': True, 'X_3': True, 'Y_0': True,
                                                       'acc': False},
                                           'summary': {'feature': True, 'label': True, 'metrics': False},
                                           'info': {'feature': ['X_0', 'X_1', 'X_2', 'X_3'], 'label': ['Y_0'],
                                                    'metrics': ['acc'],
                                                    'seq': [[0, 1]]},
                                           'score': {'feature': 1.0, 'label': 1.0, 'metrics': 0.1}},
                                          tolerance=1e-1))
        self.assertIsInstance(stats.summary(), pd.DataFrame)
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
        mon = exp.as_monitor('test', schedule='daily')
        meta = om.models.metadata('test')
        self.assertIsInstance(mon, ModelDriftMonitor)
        self.assertIn('tracking', meta.attributes)
        self.assertIn('monitors', meta.attributes['tracking'])
        self.assertIn({'experiment': 'test', 'provider': 'models',
                       'alerts': [{'event': 'drift', 'recipients': []}],
                       'schedule': 'daily', 'job': 'monitors/test/test'},
                      meta.attributes['tracking']['monitors'])
        # test getting the monitor does not add it again
        mon = exp.as_monitor('test', alerts=[{'event': 'drift', 'recipients': ['me']}])
        self.assertIsInstance(mon, ModelDriftMonitor)
        meta = om.models.metadata('test')
        self.assertIn({'experiment': 'test', 'provider': 'models',
                       'alerts': [{'event': 'drift', 'recipients': ['me']}],
                       'schedule': 'daily', 'job': 'monitors/test/test'},
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
        self.assertTrue(mon.summary(raw=True)['info']['seq'])
        meta = om.models.metadata('test')
        self.assertIsInstance(mon, ModelDriftMonitor)
        self.assertIn('tracking', meta.attributes)
        self.assertIn('monitors', meta.attributes['tracking'])
        self.assertIn({'experiment': 'test', 'provider': 'models',
                       'alerts': [{'event': 'drift', 'recipients': []}],
                       'schedule': 'daily', 'job': 'monitors/test/test'},
                      meta.attributes['tracking']['monitors'])
        # test getting the monitor does not add it again
        # -- get the monitor
        mon = exp.as_monitor('test')
        self.assertIsInstance(mon, ModelDriftMonitor)
        # -- ensure the monitor is not added again
        meta = om.models.metadata('test')
        self.assertIn({'experiment': 'test', 'provider': 'models',
                       'alerts': [{'event': 'drift', 'recipients': []}],
                       'schedule': 'daily', 'job': 'monitors/test/test'},
                      meta.attributes['tracking']['monitors'])
        self.assertEqual(len(meta.attributes['tracking']['monitors']), 1)
        # ensure the monitor job is created, run it
        self.assertIn('monitors/test/test.ipynb', om.jobs.list())
        om.runtime.job('monitors/test/test').run()
        # -- check the monitor ran and created an alert
        jobmeta = om.jobs.metadata('monitors/test/test')
        jobstatus = jobmeta.attributes['job_runs'][-1]['status']
        if jobstatus != 'OK':
            # print message for easy debugging in case of test failure
            print(jobmeta.attributes['job_runs'][-1]['message'])
        self.assertEqual(jobstatus, 'OK')
        # stats=False means we get alert events, not drift stats
        alerts = mon.events(event='alert', raw=True, stats=False)
        self.assertEqual(len(alerts), 1)
        # check the alert is as expected
        # -- remove runtime dependent keys
        # -- note that the alert's value is a list of drifts
        drifts = alerts[0]['value']
        for k in 'userid', 'dt', 'node', 'run', 'step':
            del drifts[0][k]
        exp_drift_summary = {'columns': {'acc': True},
                             'info': {'metrics': ['acc'], 'seq': [[0, 1]]},
                             'summary': {'metrics': True},
                             'score': {'metrics': .895}}
        self.assertDictEqual({'event': 'drift',
                              'experiment': 'test',
                              'key': 'test',
                              'monitor': 'test',
                              'value': exp_drift_summary}, drifts[0])
        # get the drift stats
        stats = mon.events(event='alert', stats=True)
        self.assertIsInstance(stats, DriftStats)
        self.assertIsInstance(stats.baseline('acc'), DriftStatsSeries)
        self.assertIsInstance(stats.target('acc'), DriftStatsSeries)

        # check can get back drift stats from alerts
        stats = mon.events(event='alert', stats=True)
        self.assertIsInstance(stats, DriftStats)
        self.assertDictEqual(stats.summary(raw=True), exp_drift_summary)

    def test_modeldrift_capture_nodata(self):
        om = self.om
        # create a model and track it
        # -- note we don't record any events, hence there can be no snapshot
        lm = LinearRegression()
        om.models.put(lm, 'test')
        with om.runtime.experiment('test', autotrack=True, recreate=True) as exp:
            exp.track('test', monitor=True)
            mon = exp.as_monitor('test')
        # test the monitor does not capture anything
        snapshot = mon.snapshot(since='last', ignore_empty=True)
        has_captured = mon.capture(since='last')
        self.assertIsNone(snapshot)
        self.assertFalse(has_captured)

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
            mon.snapshot(run=-1)
            om.runtime.model('regmodel').score('sample[x]', 'sample[y]').get()
            om.runtime.model('regmodel').predict('sample[x]').get()
            exp.log_data('XX', df)
            mon.snapshot(run=-1)
            mon.compare(seq='baseline').describe()

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
            mon.compare(seq='baseline').describe()

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

    def test_catcol_xy_tracking(self):
        import omegaml as om
        from sklearn import datasets
        from omegaml.backends.monitoring import ModelDriftMonitor
        x, y = datasets.load_iris(return_X_y=True, as_frame=True)
        with om.runtime.experiment('foo', recreate=True) as exp:
            mon = ModelDriftMonitor(tracking=exp)
            snapshot = mon.snapshot(X=x, Y=y, catcols=['target'])
            self.assertIn('X', snapshot)
            self.assertIn('Y', snapshot)
            # note the column is renamed to Y_target (to make it unique among all columns)
            self.assertIn('Y_target', snapshot['Y']['info']['cat_columns'])

    def test_most_recent_snapshot(self):
        """ get the most recent snapshots and respective time """
        om = self.om
        with om.runtime.experiment('test') as exp:
            mon = DataDriftMonitor('foo', store=om.datasets, tracking=exp)
        df = pd.DataFrame({
            'x': np.random.uniform(0, 1, 100),
        })
        # -- no snapshot
        self.assertEqual(datetime.datetime.min, mon._most_recent_snapshot_time())
        # -- test various snapshot ranges
        for i in range(5):
            snapshot1 = mon.snapshot(df)
            snapshot2 = mon.snapshot(df)
            self.assertEqual(snapshot1['info'], mon._most_recent_snapshots(n=2)[-2]['info'])
            self.assertEqual(snapshot2['info'], mon._most_recent_snapshots(n=2)[-1]['info'])
            self.assertEqual(snapshot1['info']['dt'], mon._most_recent_snapshot_time(n=2))
            self.assertEqual(snapshot2['info']['dt'], mon._most_recent_snapshot_time())

    def test_model_snapshot_since(self):
        """ automatically snapshot model metrics, X, Y from multiple subsequent runs """
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
            mon = exp.as_monitor('regmodel')
            mon.snapshot(event='fit')
            latest_snapshot_dt = mon._most_recent_snapshot_time()
        for i in range(10):
            # force multiple runs
            om.runtime.model('regmodel').predict('sample[x]').get()
        # snapshot all predict events since last snapshot
        # -- expect to get all predict events since last
        snapshot = mon.snapshot(event='predict', since='last')
        self.assertEqual(snapshot['info']['since'], latest_snapshot_dt)
        self.assertEqual(snapshot['X']['info']['len'], 10 * len(df))
        self.assertEqual(snapshot['Y']['info']['len'], 10 * len(df))
        # snapshot all predict events since last snapshot
        # -- should raise assertion error since there are no predict events since last
        with self.assertRaises(AssertionError) as cm:
            mon.snapshot(event='predict', since='last')
        self.assertIn('no model events using query', str(cm.exception))
        mon.capture(since='last')

    def test_snapshot_since_dt_datamonitor(self):
        om = self.om
        df = pd.DataFrame({
            'x': range(1, 10)
        })
        with om.runtime.experiment('myexp', autotrack=True) as exp:
            mon = DataDriftMonitor('foo', store=om.datasets, tracking=exp)
            mon.snapshot(df)
            mon.snapshot(df)
            mon.snapshot(df)
        data = exp.data()
        start = data.iloc[0]['dt']
        # specify since using a datetime that selects all snapshots
        stats = mon.compare('baseline', since=start)
        self.assertEqual(len(stats['x', 'mean']), 2)  # 3 snapshots => 2 comparisons
        # specify since using a datetime that selects no snapshots
        stats = mon.compare('baseline', since=pd.to_datetime('now'))
        df = stats.as_dataframe(column='x')
        self.assertEqual(len(df), 0)

    def test_snapshot_since_dt_modelmonitor(self):
        om = self.om
        df = pd.DataFrame({
            'x': range(1, 10)
        })
        with om.runtime.experiment('myexp', autotrack=True) as exp:
            mon = ModelDriftMonitor('foo', store=om.datasets, tracking=exp)
            mon.snapshot(X=df)
            mon.snapshot(X=df)
            mon.snapshot(X=df)
        data = exp.data()
        start = data.iloc[0]['dt']
        # specify since using a datetime that selects all snapshots
        stats = mon.compare('baseline', since=start)
        self.assertEqual(len(stats['X_x', 'mean']), 2)  # 3 snapshots => 2 comparisons
        # specify since using a datetime that selects no snapshots
        stats = mon.compare('baseline', since=pd.to_datetime('now'))
        df = stats.as_dataframe(column='X_x')
        self.assertEqual(len(df), 0)

    def test_correlations(self):
        om = self.om
        with om.runtime.experiment('test') as exp:
            mon = DataDriftMonitor('foo', store=om.datasets, tracking=exp)
            mon.clear(force=True)
            mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', correlate=True)
        data = mon.data[-1]
        self.assertIn('corr', data['stats']['lifeExp'])
        self.assertIn('pearson', data['stats']['lifeExp']['corr'])
        self.assertIn('spearman', data['stats']['lifeExp']['corr'])
        df = om.datasets.get('gapminder')[['lifeExp', 'gdpPercap', 'pop']]
        stats = mon.compare()
        for method in 'pearson', 'spearman':
            # we have to sort columns and index to ensure the comparison is correct
            # -- DriftStatsDataFrame sorts columns and index in the same way
            corr_expected = df[sorted(df.columns)].corr(method=method).sort_index()
            corr_stored = stats.baseline().corr(method=method)
            assert_frame_equal(corr_stored, corr_expected)

    def test_multilevel_naming(self):
        # test fix issue #452
        om = self.om
        reg = LinearRegression()
        om.models.put(reg, 'myapp/regmodel')
        # create a new experiment
        with om.runtime.experiment('myapp/regmodel') as exp:
            exp.track('myapp/regmodel', monitor=True)
            exp.log_data('test', 42)
        self.assertTrue(exp._has_monitor('myapp/regmodel'))
        # try again (retrieving the experiment)
        with om.runtime.experiment('myapp/regmodel') as exp:
            # self.assertTrue(exp._has_monitor('myapp/regmodel'))
            exp.track('myapp/regmodel', monitor=True)
            exp.log_data('test2', 42)
        meta = om.models.metadata('myapp/regmodel')
        monitors = meta.attributes['tracking']['monitors']
        self.assertEqual(len(monitors), 1)
        # get the experiment without starting it
        exp = om.runtime.experiment('myapp/regmodel')
        self.assertTrue(exp._has_monitor('myapp/regmodel'))
        # get data recorded in second run
        data = exp.data(run='*', event='data', key='test2')
        self.assertEqual(len(data), 1)
        self.assertEqual(data.iloc[0]['value']['data'], 42)
        # get data recorded in first run
        data = exp.data(run='*', event='data', key='test')
        self.assertEqual(len(data), 1)
        self.assertEqual(data.iloc[0]['value']['data'], 42)
        self.assertEqual(exp.dataset, '.experiments/myapp/regmodel')
        # test backwards compatibility
        # -- create a dataset using the basename (regmodel)
        om.models.put(reg, 'myapp/regmodel2')
        exp = om.runtime.experiment('myapp/regmodel2')
        exp.experiment._experiment = 'regmodel2'  # simuate pre-fix behavior
        exp.start()
        exp.track('myapp/regmodel2', monitor=True)
        exp.log_data('test', 48)
        exp.stop()
        self.assertEqual(exp.dataset, '.experiments/regmodel2')
        # -- get back the experiment using the basename (backwards compatibility)
        exp = om.runtime.experiment('myapp/regmodel2')
        self.assertEqual(exp.dataset, '.experiments/regmodel2')
        data = exp.data(run='*', event='data', key='test')
        self.assertEqual(len(data), 1)
        self.assertEqual(data.iloc[0]['value']['data'], 48)
        # check we migrate to the name behavior if in conflict
        # -- force new behavior
        exp = om.runtime.experiment('myapp/regmodel2')
        exp.experiment._experiment = 'myapp/regmodel2'
        self.assertEqual(exp.dataset, '.experiments/myapp/regmodel2')
        exp.start()
        exp.track('myapp/regmodel2', monitor=True)
        exp.log_data('test', 52)
        exp.stop()
        # -- test conflict resolution is to new name
        exp = om.runtime.experiment('myapp/regmodel2')
        self.assertEqual(exp.dataset, '.experiments/myapp/regmodel2')
        data = exp.data(run='*', event='data', key='test')
        self.assertEqual(len(data), 1)
        self.assertEqual(data.iloc[0]['value']['data'], 52)
