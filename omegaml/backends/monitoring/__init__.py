from itertools import product, pairwise

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp, chisquare
from datetime import datetime


class DriftStatsCalc:
    def ks_2samp(self, d1, d2, ci=.95):
        # two-sample Kolmogorov-Smirnov test for goodness of fit
        # -- H0: d1, d2 are from the same distribution (=> no drift)
        # -- H1: alternative (=> drift) 
        # -- H0 is rejected if pvalue < 1 - ci (default: 0.05)
        # https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ks_2samp.html
        result = ks_2samp(d1, d2)
        is_drift = result.pvalue < (1 - ci)
        return {
            'metric': result.statistic,
            'drift': is_drift,
            'pvalue': result.pvalue,
            'location': result.statistic_location,
        }

    def chisquare(self, d1, d2, ci=.99):
        # one-way chi-square test
        # -- H0: categorical frequencies in d2 match the expectation in d1 (=> no drift)
        # -- H1: alterantive (=> drift)
        # -- H0 is rejected if pvalue < 1 
        # https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chisquare.html#scipy.stats.chisquare
        result = chisquare(f_obs=d2, f_exp=d1)
        is_drift = result.pvalue < 1
        return {
            'metric': result.statistic,
            'drift': is_drift,
            'pvalue': result.pvalue,
            'location': None,
        }


class DriftMonitorBase:
    def __init__(self, name, resource=None, store=None, query=None, **kwargs):
        self.name = name
        self.store = store
        self._resource = resource
        self._query = query or kwargs

    def snapshot(self, *args, **kwargs):
        raise NotImplementedError

    def drift(self, seq=None, d1=None, d2=None, ci=.95):
        seq = seq or [-2, -1]
        recursive_seq = isinstance(seq, (list, tuple)) and len(seq) > 2
        template_seq = seq in (True, 'baseline', 'series')
        if recursive_seq or template_seq:
            # return a drift history
            if seq is True or seq == 'series':
                # [0, 1, 2, ...] => compare each snapshot to the previous
                seq = range(0, len(self)) if seq is True else seq
                drifts = [self.drift(seq=[i, j], ci=ci) for i, j in pairwise(seq)]
            elif seq == 'baseline':
                # [0, 1], [0, 2], [0, 3], ... => compare each snapshot to the baseline
                seq = list(product([0], range(1, len(self))))
                drifts = [self.drift(seq=pair, ci=ci) for pair in seq]
            else:
                raise ValueError(f'invalid drift sequence {seq}, must be True, "baseline", "series" or a list of snapshot indices.')
            return drifts
        if d1 or d2:
            s1 = self.snapshot(d1) if d1 else None
            s2 = self.snapshot(d2) if d2 else None
        else:
            s1, s2 = None, None
        if not all((s1, s2)):
            snapshots = self.data()
            if len(snapshots) > 1:
                _s1 = snapshots[seq[0]]
                _s2 = snapshots[seq[1]]
            else:
                _s1 = _s2 = snapshots[seq[-1]]
        s1 = s1 or _s1
        s2 = s2 or _s2
        drift = self._calc_drift(s1, s2, ci=ci)
        drift['info']['seq'] = list(seq)
        return drift

    @property
    def dataset(self):
        return f'.monitor/{self.name}'

    def data(self):
        # TODO use tracking.data(event='snapshot')
        return self.store.get(self.dataset)

    def report(self, seq=None, format='html'):
        data = self.drift(seq=seq)
        FORMATS = {
            'html': lambda v: pd.json_normalize(v).T.to_html(),
            'json': lambda v: pd.DataFrame(v).to_json(),
            'dict': lambda v: data,
        }
        return FORMATS[format](data) if format in FORMATS else data

    def clear(self):
        self.store.drop(self.dataset, force=True)

    def __len__(self):
        # make more efficient
        return len(self.data())

    def _do_snapshot(self, df1: pd.DataFrame, columns=None):
        df1 = df1[columns] if columns else df1
        numeric_columns = list(df1.select_dtypes(include='number').columns)
        cat_columns = list(set(df1.columns) - set(numeric_columns))

        snapshot = {}
        stats = snapshot.setdefault('stats', {})
        info = snapshot.setdefault('info', {})
        info['num_columns'] = numeric_columns
        info['cat_columns'] = cat_columns
        info['dt'] = datetime.utcnow().isoformat()
        for col in numeric_columns:
            stats[col] = {
                'dtype': str(df1.dtypes[col]),
                'hist': np.histogram(df1[col].values)
            }
        for col in cat_columns:
            stats[col] = {
                'dtype': str(df1.dtypes[col]),
                'groups': df1[col].value_counts().to_dict()
            }
        # TODO report in tracking, not here
        # -- tracking.log_snapshot() ?
        self.store.put(snapshot, self.dataset)
        return snapshot

    def _calc_drift(self, s1, s2, ci=.95):
        calc = DriftStatsCalc()
        numeric_columns = s1['info']['num_columns']
        cat_columns = s1['info']['cat_columns']
        drift = {}
        info = drift.setdefault('info', {})
        metrics = drift.setdefault('stats', {})
        result = drift.setdefault('result', {})
        for col in numeric_columns:
            d1 = s1['stats'][col]['hist'][0]
            d2 = s2['stats'][col]['hist'][0]
            metrics[col] = {
                # KS statistic, p_value
                # https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ks_2samp.html
                'ks': calc.ks_2samp(d1, d2, ci=ci),
            }
        for col in cat_columns:
            g1 = s1['stats'][col]['groups']
            g2 = s2['stats'][col]['groups']
            # calculate group frequencies (%), required for chisquare
            g1v = np.array(list(g1.values()))
            g2v = np.array(list(g2.get(g, 0) for g in g1))
            d1 = (np.array(g1v) / np.sum(g1v)).round(decimals=99)
            d2 = (np.array(g2v) / np.sum(g2v)).round(decimals=99)
            metrics[col] = {
                # https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chisquare.html
                'chisq': calc.chisquare(d1, d2, ci=ci)
            }
        # add meta information about this drift
        info['dt_from'] = s1['info'].get('dt')
        info['dt_to'] = s2['info'].get('dt')
        info['ci'] = ci
        info['baseline'] = s1['info']
        info['target'] = s2['info']
        # summarize drift metrics
        # -- per column: mean of drift statistics (1 = drift, 0 = no drift)
        # -- per dataset: mean of column drift statistics
        # -- that is, info['drift'] is the mean of all column drift indicators (0 = no drift, > 0 = drift)
        # per column
        for col in numeric_columns + cat_columns:
            col_stats = metrics[col]
            mean_stats = col_stats.setdefault('mean', {})
            mean_stats['metric'] = np.mean([v['drift'] for v in col_stats.values() if v])
            mean_stats['stats'] = [k for k, v in col_stats.items() if v.get('drift')]
            mean_stats['drift'] = mean_stats['metric'] > 0
        # per dataset
        column_drifts = [v['mean']['drift'] for v in metrics.values()]
        result['drift'] = any(column_drifts)
        result['method'] = 'mean'
        result['metric'] = np.mean(column_drifts)
        result['columns'] = [col for col in numeric_columns + cat_columns if metrics[col]['mean']['drift']]
        return drift


class DataDriftMonitor(DriftMonitorBase):
    def __init__(self, name, dataset=None, store=None, query=None, **kwargs):
        super().__init__(name, resource=dataset, store=store, query=query, **kwargs)

    def snapshot(self, dataset=None, chunksize=None, columns=None, **query):
        # TODO: for chunksizes need to combine hist for multiple chunks
        # -- https://stackoverflow.com/a/57884457/890242
        dataset = dataset or self._resource
        query = query or self._query
        if isinstance(dataset, pd.DataFrame):
            df = dataset
        else:
            df = self.store.get(dataset, **query)
        snapshot = self._do_snapshot(df, columns=columns)
        return snapshot


