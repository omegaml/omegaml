from unittest import TestCase

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from omegaml.backends.monitoring import DataDriftMonitor, ModelMonitor
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

    def test_datadrift(self):
        om = self.om
        mon = DataDriftMonitor('foo', store=om.datasets)
        df = pd.DataFrame({
            'x': np.random.uniform(0, 1, 100),
        })
        snapshot = mon.snapshot(df)
        self.assertIn('stats', snapshot)
        self.assertIn('info', snapshot)
        self.assertIn('num_columns', snapshot['info'])
        self.assertEqual(snapshot['info']['num_columns'], ['x'])
        self.assertEqual(snapshot['info']['cat_columns'], [])
        data = mon.data()
        self.assertEqual(len(data), 1)
        drift = mon.drift()
        self.assertIn('info', drift)
        self.assertIn('stats', drift)
        self.assertEqual(drift['info']['seq'], [-1, -1])
        self.assertEqual(drift['result']['drift'], False)

    def test_datadrift_drift(self):
        om = self.om
        mon = DataDriftMonitor('foo', store=om.datasets)
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
        data = mon.data()[-1]
        for col in df.columns:
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
        mon = DataDriftMonitor('foo', store=om.datasets)
        mon.clear()
        df = self.df
        # -- baseline
        mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', year__lte=1960)
        # -- a number of snapshots
        mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', year__lte=1970)
        mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', year__lte=1980)
        mon.snapshot('gapminder[lifeExp,gdpPercap,pop]', year__gt=1980)
        # -- get all drifts since baseline
        drifts = mon.drift(seq=True)
        # expect 3 drift calculations
        self.assertEqual(len(drifts), 3)
        # -- 1960/1970, 1970/1980, 1980/now
        self.assertEqual(drifts[0]['info']['seq'], [0, 1])
        self.assertEqual(drifts[1]['info']['seq'], [1, 2])
        self.assertEqual(drifts[2]['info']['seq'], [2, 3])
        # -- expect drifts in 1960/1970 and 1980/now
        self.assertEqual(drifts[0]['result']['drift'], True)
        self.assertEqual(drifts[1]['result']['drift'], False)
        self.assertEqual(drifts[2]['result']['drift'], True)
        # -- expect drifts in lifeExp (1960/1980) and gdpPercap (1980/now)
        self.assertEqual(drifts[0]['result']['columns'], ['lifeExp'])
        self.assertEqual(drifts[1]['result']['columns'], [])
        self.assertEqual(drifts[2]['result']['columns'], ['gdpPercap'])

    def test_datadrift_vs_baseline(self):
        om = self.om
        mon = DataDriftMonitor('foo', store=om.datasets)
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
        drifts = mon.drift(seq='baseline')
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
        self.assertEqual(drifts[1]['result']['columns'], ['lifeExp'])
        self.assertEqual(drifts[2]['result']['columns'], ['lifeExp', 'gdpPercap'])

    def _setup_model(self):
        om = self.om
        with om.runtime.experiment('test') as exp:
            #exp.clear(force=True)
            for i in range(100):
                exp.start()
                if i == 0:
                    X = np.array(np.random.random(size=(10, 4)))
                    y = np.dot(X, np.random.random(size=(4, 1))) + np.random.random()
                    lm = LinearRegression()
                    lm.fit(X, y)
                else:
                    y = np.dot(X, np.random.random(size=(4, 1)) * 1000) + np.random.random()
                exp.log_metric('acc', lm.score(X[5:], y[5:]))
                exp.stop()

        return exp
        acc = exp.data(run='all', event='metric', key='acc')['value']
        # (acc
        #  .transform(lambda s: (s - s.mean()) / s.std())
        #  .hist())


    def test_model_drift(self):
        om = self.om
        exp = self._setup_model()
        mon = ModelMonitor('modelmon', 'foo', tracking=exp, store=om.datasets)
        mon.snapshot(run=[-1])
        mon.drift(seq=[0] + list(range(-3, 0)), ci=.9)


