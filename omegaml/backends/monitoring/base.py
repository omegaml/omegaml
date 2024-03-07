import numpy as np
import pandas as pd
from datetime import datetime
from itertools import pairwise, product

from omegaml.backends.monitoring.stats import DriftStats, DriftStatsCalc


class DriftMonitorBase:
    def __init__(self, name, resource=None, store=None, query=None, tracking=None, **kwargs):
        self.name = name
        self.store = store
        self._resource = resource
        self._query = query or kwargs
        self.tracking = tracking

    def snapshot(self, *args, **kwargs):
        raise NotImplementedError

    def drift(self, seq=None, d1=None, d2=None, ci=.95, raw=False):
        recursive_seq = isinstance(seq, (list, tuple)) and len(seq) > 2
        template_seq = seq in (True, 'baseline', 'series')
        if recursive_seq or template_seq:
            # return a drift history (call this method recursively)
            if recursive_seq or seq in (True, 'series'):
                # [0, 1, 2, ...] => compare each snapshot to the previous
                seq = range(0, len(self)) if seq is True else seq
                drifts = [self._single_drift(seq=[i, j], ci=ci, raw=True) for i, j in pairwise(seq)]
            elif seq == 'baseline':
                # [0, 1], [0, 2], [0, 3], ... => compare each snapshot to the baseline
                seq = list(product([0], range(1, len(self))))
                drifts = [self._single_drift(seq=pair, ci=ci, raw=True) for pair in seq]
            else:
                raise ValueError(
                    f'invalid drift sequence {seq}, must be True, "baseline", "series" or a list of snapshot indices.')
            drifts = [d for d in drifts if d is not None]
            return DriftStats(drifts) if not raw else drifts
        return self._single_drift(seq=seq, d1=d1, d2=d2, ci=ci, raw=raw)

    def _single_drift(self, seq=None, d1=None, d2=None, ci=.95, raw=False):
        # return a single drift
        if d1 or d2:
            s1 = self.snapshot(d1) if d1 else None
            s2 = self.snapshot(d2) if d2 else None
            seq = seq or [-2, -1]
        else:
            s1, s2 = None, None
            seq = seq or []
        if not all((s1, s2)):
            # TODO snapshot querying should be in self.data(), not here
            #      to be scalable
            snapshots = self.data
            if snapshots is None or len(snapshots) < 1:
                # no snapshots, no drift
                return None
            if len(snapshots) > 1:
                seq = seq or [-2, -1]
                _s1 = snapshots[seq[0]]
                _s2 = snapshots[seq[1]]
            else:
                seq = seq or [-1, -1]  # always specify from/to
                _s1 = _s2 = snapshots[seq[-1]]
            s1 = s1 or _s1
            s2 = s2 or _s2
        drift = self._calc_drift(s1, s2, ci=ci)
        eff_seq = lambda s: s if s >= 0 else len(snapshots) + s
        drift['info']['seq'] = [eff_seq(seq[0]), eff_seq(seq[1])]
        return DriftStats(drift) if not raw else drift

    @property
    def dataset(self):
        return f'.monitor/{self.name}'

    @property
    def data(self):
        # TODO use tracking.data(event='snapshot')
        return self.store.get(self.dataset)

    def report(self, seq=None, format='html'):
        data = self.drift(seq=seq, raw=True)
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
        return len(self.data or [])

    def _do_snapshot(self, df1: pd.DataFrame, columns=None, name=None, kind=None, info=None, _prefix=None):
        extra_info = info or {}
        df1 = df1[columns] if columns else df1
        numeric_columns = list(df1.select_dtypes(include='number').columns)
        cat_columns = list(set(df1.columns) - set(numeric_columns))
        snapshot = {}
        stats = snapshot.setdefault('stats', {})
        info = snapshot.setdefault('info', {})
        info['resource'] = name
        info['kind'] = kind
        info['num_columns'] = numeric_columns if not _prefix else [f'{_prefix}_{col}' for col in numeric_columns]
        info['cat_columns'] = cat_columns if not _prefix else [f'{_prefix}_{col}' for col in cat_columns]
        info['dt'] = datetime.utcnow().isoformat()
        for col in numeric_columns:
            s_col = col if not _prefix else f'{_prefix}_{col}'
            values = df1[col].values
            bins = 10 if len(values) < 1000 else 100
            probs = [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, .95]
            stats[s_col] = {
                'dtype': str(df1.dtypes[col]),
                'hist': np.histogram(values, bins=bins, density=False),
                'std': np.std(values),
                'mean': np.mean(values),
                'min': np.min(values),
                'max': np.max(values),
                'percentiles': [np.quantile(values, probs), probs],
            }
        for col in cat_columns:
            s_col = col if not _prefix else f'{_prefix}_{col}'
            stats[s_col] = {
                'dtype': str(df1.dtypes[col]),
                'groups': df1[col].value_counts().to_dict()
            }
        snapshot['info'].update(extra_info)
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
            # ks_2samp: two-sample Kolmogorov-Smirnov test for goodness of fit
            # -- we compare the cumulative histograms of the two datasets
            # -- hist[0] is the frequences for each bin
            # -- hist[1] is the bin edges
            h1, e1 = s1['stats'][col]['hist']
            h2, e2 = s2['stats'][col]['hist']
            sd = s1['stats'][col]['std']
            samples = 100 if len(e1) < 100 else 1000
            d1 = calc.sample_from_hist(h1, e1, n=samples)
            d2 = calc.sample_from_hist(h2, e2, n=samples)
            cdf1 = calc.cdf_from_hist(h1, e1)
            cdf2 = calc.cdf_from_hist(h2, e2)
            metrics[col] = {
                # KS statistic, p_value
                # https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ks_2samp.html
                'ks': calc.ks_2samp(d1, d2, ci=ci),
                'wasserstein': calc.wasserstein_distance(d1, d2, ci=ci, sd=sd),
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
        info['baseline'] = s1
        info['target'] = s2
        # summarize drift metrics
        # -- per column: mean of drift statistics (1 = drift, 0 = no drift)
        # -- per dataset: mean of column drift statistics
        # -- that is, info['drift'] is the mean of all column drift indicators (0 = no drift, > 0 = drift)
        # per column
        for col in numeric_columns + cat_columns:
            col_stats = metrics[col]
            mean_stats = {}
            mean_stats['metric'] = np.mean([v['drift'] for v in col_stats.values() if v])
            mean_stats['score'] = np.mean([v['score'] for v in col_stats.values() if v])
            mean_stats['stats'] = [k for k, v in col_stats.items() if v.get('drift')]
            mean_stats['drift'] = mean_stats['metric'] > 0
            col_stats['mean'] = mean_stats
        # per dataset
        column_drifts = [v['mean']['drift'] for v in metrics.values()]
        column_scores = [v['mean']['score'] for v in metrics.values()]
        result['drift'] = any(column_drifts)
        result['method'] = 'mean'
        result['metric'] = np.mean(column_drifts)
        result['metric'] = np.mean(column_scores)
        result['columns'] = [col for col in numeric_columns + cat_columns if metrics[col]['mean']['drift']]
        return drift

    def capture(self, column=None, statistic=None):
        """
        capture detected drift, if any, by logging an event in tracking

        This method is called by a drift detection job to log a drift event in
        the tracking system. It logs a 'drift' event with the resource name
        as the event key, and the drift indicator as the event value. Extra
        information is logged to link back to the monitoring system, such as
        the monitor name, the sequence number and the column that drifted.

        To retrieve the drift events, use the tracking system to query for
        events of type 'drift' and the resource name as the event key::

            tracking.data(event='drift', key='resource_name')

        Args:
            column (str): the column that drifted, optional
            statistic (str): the statistic that drifted, optional

        Returns:
            bool: True if drift was detected and logged, False otherwise
        """
        drift = self.drift()
        event =  drift.drifted(column=column, statistic=statistic, summary=True)
        if any(drifted for part, drifted in event.items()):
            extra = {
                'seq': drift.seq(),
                'column': column or '*',
                'monitor': self.name,
            }
            self.tracking.log_event('drift', self._resource, event, **extra)
            return True
        return False

