import numpy as np
import pandas as pd
from datetime import datetime
from itertools import pairwise, product

from omegaml.backends.monitoring.alerting import AlertRule
from omegaml.backends.monitoring.stats import DriftStats, DriftStatsCalc


class DriftMonitorBase:
    def __init__(self, resource=None, store=None, query=None, tracking=None, kind=None, **kwargs):
        self.store = store
        self._resource = resource
        self._query = query or kwargs
        self._kind = kind
        self.tracking = tracking
        self.samples = [1000, 10000]  # small and large sample sizes

    def __repr__(self):
        return f'{self.__class__.__name__}({self._resource})'

    @property
    def df(self):
        return pd.json_normalize(self.data)

    def snapshot(self, *args, **kwargs):
        raise NotImplementedError

    def drifted(self, seq=None, d1=None, d2=None, ci=.95, raw=False, column=None, statistic=None, summary=False):
        seq = seq or 'baseline'
        drift = self.drift(seq=seq, d1=d1, d2=d2, ci=ci, raw=raw)
        return drift.drifted(column=column, statistic=statistic, summary=summary)

    def compare(self, *args, **kwargs):
        """ calculate drift

        Args:
            seq (list|str): a list of snapshot indices to compare in the format [i, j],
               or one of 'baseline', 'series'. Use 'baseline' to compare every snapshot
               to the first snapshot, or 'series' to compare each snapshot to the previous.
               [i, j] are 0-indexed snapshot indices, can be specified as negative indices
               to indicate the last n-th snapshot.
            d1 (int): the first snapshot index to compare, optional
            d2 (int): the second snapshot index to compare, optional
            ci (float): the confidence interval for the drift test, defaults to .95
            baseline (int): the baseline snapshot index to compare to, defaults to 0
            raw (bool): if True, returns drift statistics as a dict, otherwise
                returns a DriftStats instance
            matcher (dict): a dict that maps columns 'old' => 'new', e.g. {'Y_y': 'Y_0'}.
               this is useful to map columns from one snapshot to another, e.g. when
               column names change between snapshots. Pass as dict(d1={...}, d2={...})
               to specifically map columns for the first and second snapshot. By default
               columns present in d1 but missing in d2 are auto-matched by position.

        Returns:
            DriftStats|[dict]: a drift statistics instance (if raw=False), or a list of dicts
        """
        return self.drift(*args, **kwargs)

    def drift(self, seq=None, d1=None, d2=None, ci=.95, baseline=0, raw=False, matcher=None):
        recursive_seq = isinstance(seq, (list, tuple)) and len(seq) > 2
        template_seq = seq in (True, 'baseline', 'series')
        if recursive_seq or template_seq:
            # return a drift history (call this method recursively)
            if recursive_seq or seq in (True, 'series'):
                # [0, 1, 2, ...] => compare each snapshot to the previous
                seq = range(0, len(self))
                drifts = [self._single_drift(seq=[i, j], ci=ci, raw=True) for i, j in pairwise(seq)]
            elif seq == 'baseline':
                # [0, 1], [0, 2], [0, 3], ... => compare each snapshot to the baseline
                seq = list(product([baseline], range(1, len(self))))
                drifts = [self._single_drift(seq=pair, ci=ci, raw=True) for pair in seq]
            else:
                raise ValueError(
                    f'invalid drift sequence {seq}, must be True, "baseline", "series" or a list of snapshot indices.')
            drifts = [d for d in drifts if d is not None]
            return DriftStats(drifts, monitor=self) if not raw else drifts
        return self._single_drift(seq=seq, d1=d1, d2=d2, ci=ci, raw=raw, matcher=matcher)

    def _single_drift(self, seq=None, d1=None, d2=None, ci=.95, raw=False, matcher=None):
        # return a single drift
        if any(d is not None for d in (d1, d2)):
            s1 = self.snapshot(d1, logged=False) if d1 is not None else None
            s2 = self.snapshot(d2, logged=False) if d2 is not None else None
            seq = seq or [0, 1]
        else:
            s1, s2 = None, None
            seq = seq or []
        snapshots = self.data
        if not all((s1, s2)):
            # TODO snapshot querying should be in self.data(), not here
            #      to be scalable
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
        drift = self._calc_drift(s1, s2, ci=ci, matcher=matcher)
        eff_seq = lambda s: s if s >= 0 else len(snapshots) + s
        drift['info']['seq'] = [eff_seq(seq[0]), eff_seq(seq[1])]
        return DriftStats(drift, monitor=self) if not raw else drift

    @property
    def dataset(self):
        return f'.monitor/{self._resource}'

    @property
    def _drift_alert_key(self):
        return f'drift:{self._resource}'

    @property
    def data(self):
        df = self.tracking.data(run='all', event='snapshot', key=self._resource, kind=self._kind)
        return df['value'].to_list() if not df.empty else []

    def report(self, seq=None, format='html'):
        data = self.drift(seq=seq, raw=True)
        FORMATS = {
            'html': lambda v: pd.json_normalize(v).T.to_html(),
            'json': lambda v: pd.DataFrame(v).to_json(),
            'dict': lambda v: data,
        }
        return FORMATS[format](data) if format in FORMATS else data

    def clear(self, force=False):
        self.tracking.clear(force=force)

    def __len__(self):
        # make more efficient
        return len(self.data or [])

    def _snapshot_info(self, name, kind, **kwargs):
        info = {
            'resource': name if isinstance(name, str) else str(type(name)),
            'kind': kind or self._kind,
            'dt': datetime.utcnow().isoformat()
        }
        info.update(kwargs)
        return info

    def _do_snapshot(self, df1: pd.DataFrame, columns=None, name=None, kind=None, info=None, _prefix=None,
                     catcols=None):
        # TODO allow specification of category columns, e.g. categorical=['col1', 'col2']
        extra_info = info or {}
        df1 = df1[columns] if columns else df1
        catcols = [c for c in catcols if c in df1.columns] if catcols else []
        numeric_columns = list(set(df1.select_dtypes(include='number').columns) - set(catcols))
        cat_columns = list(set(df1.columns) - set(numeric_columns))
        snapshot = {}
        stats = snapshot.setdefault('stats', {})
        info = snapshot.setdefault('info', self._snapshot_info(name, kind, **extra_info))
        info['num_columns'] = numeric_columns if not _prefix else [f'{_prefix}_{col}' for col in numeric_columns]
        info['cat_columns'] = cat_columns if not _prefix else [f'{_prefix}_{col}' for col in cat_columns]
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
        return snapshot

    def _log_snapshot(self, snapshot):
        self.tracking.use()  # ensure we have an active run
        self.tracking.log_event('snapshot', self._resource, snapshot, kind=snapshot['info']['kind'])

    def _log_drift(self, drift, **extra):
        self.tracking.use()  # ensure we have an active run
        self.tracking.log_event('drift', self._resource, drift, **extra)

    def _calc_drift(self, s1, s2, ci=.95, matcher=None):
        calc = DriftStatsCalc()
        numeric_columns = s1['info']['num_columns']
        cat_columns = s1['info']['cat_columns']
        drift = {}
        info = drift.setdefault('info', {})
        metrics = drift.setdefault('stats', {})
        sample = drift.setdefault('sample', {})
        result = drift.setdefault('result', {})
        # specific or auto column name matcher
        # -- auto matches columns by position
        # -- in particular Y_y => Y_0, Y_1, ...
        # -- only applies to columns in s1['stats'] that are not in s2['stats']
        auto_matcher = {k: v for k, v in zip(s1['stats'].keys(), s2['stats'].keys())}
        matcher = matcher or auto_matcher
        _c = lambda d, s, c: matcher.get(d, matcher).get(c, c) if c not in s['stats'] else c
        info.setdefault('columns_map', {}).update(matcher)
        for col in numeric_columns:
            # ks_2samp: two-sample Kolmogorov-Smirnov test for goodness of fit
            # -- we compare the cumulative histograms of the two datasets
            # -- hist[0] is the frequences for each bin
            # -- hist[1] is the bin edges
            h1, e1 = s1['stats'][_c('d1', s1, col)]['hist']
            h2, e2 = s2['stats'][_c('d2', s2, col)]['hist']
            sd = s1['stats'][_c(None, s1, col)]['std']
            samples = self.samples[0] if len(e1) < 100 else self.samples[1]
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
            sample[col] = {
                'd1': d1,
                'd2': d2,
            }
        for col in cat_columns:
            g1 = s1['stats'][_c('d1', s1, col)]['groups']
            g2 = s2['stats'][_c('d2', s2, col)]['groups']
            # calculate group frequencies (%), required for chisquare
            g1v = np.array(list(g1.values()))
            g2v = np.array(list(g2.get(g, 0) for g in g1))
            d1 = (np.array(g1v) / np.sum(g1v)).round(decimals=99)
            d2 = (np.array(g2v) / np.sum(g2v)).round(decimals=99)
            metrics[col] = {
                # https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chisquare.html
                'chisq': calc.chisquare(d1, d2, ci=ci),
            }
            sample[col] = {
                'd1': d1,
                'd2': d2,
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

    def check(self, alerts=None, notify=True):
        """ check for drift and notify recipients

        Args:
            alerts (list): a list of alert rules
            notify (bool): whether to notify recipients, defaults to True
        """
        rules = self._make_alert_rules(alerts or [{
            'event': 'drift',
            'action': 'notify',
            'recipients': ['users'],
        }])
        for rule in rules:
            rule.check(notify=notify, run=self.tracking.active_run())

    def capture(self, column=None, statistic=None, alerts=None, seq='baseline', baseline=0):
        """
        capture detected drift, if any, by logging an event in tracking

        This method is called by a monitor job to log a drift event in
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
            alerts (list): a list of alert rules to apply, optional
            seq (str): the sequence to compare to, defaults to 'baseline'
            baseline (int): the baseline sequence to compare to, defaults to 0

        Returns:
            bool: True if drift was detected and logged, False otherwise
        """
        drift = self.drift(seq=seq, baseline=baseline)
        event = drift.drifted(column=column, statistic=statistic, summary=True)
        if any(drifted for part, drifted in event.items()):
            extra = {
                'seq': drift.seq(),
                'column': column or '*',
                'monitor': self._resource,
            }
            self._log_drift(event, **extra)
            self.check(alerts)
            return True
        return False

    def _make_alert_rules(self, alerts):
        # ensure we have a list of AlertRule instances
        rules = []
        for alert in alerts:
            rule = AlertRule(monitor=self, **alert) if not isinstance(alert, AlertRule) else alert
            rules.append(rule)
        return rules

    def alerts(self, run=None, since=None, raw=False, stats=False):
        run = run or '*'
        data = self.tracking.data(run=run, event='alert', key=self._drift_alert_key,
                                  since=None)
        if not raw and stats:
            # -- data['value'] is a series of dicts, each dict is a drift event
            # -- each drift event is a list of drift indicators, see .capture()
            # -- 'seq' is the respective (min, max) sequence associated with the drift event
            # ==> drifted_seqs is the list of (min, max) sequence numbers to recalculate the drifts
            drifted_seqs = data.explode('value')['value'].apply(lambda v: v['seq']).to_list()
            drifts = [self.drift(seq=seq, raw=True) for seq in drifted_seqs]
            return DriftStats(drifts, monitor=self)
        return data if not raw else data.to_dict(orient='records')

    def captured(self, column=None, statistic=None, run=None, since=None, stats=True, raw=False):
        run = run or '*'
        column = column or '*'
        data = self.tracking.data(run=run, event='drift', key=self._resource, since=since,
                                  column=column, statistic=statistic)
        if not raw and stats:
            # -- each drift event is a list of drift indicators, see .capture()
            # -- 'seq' is the respective (min, max) sequence associated with the drift event
            # ==> drifted_seqs is the list of (min, max) sequence numbers to recalculate the drifts
            drifted_seqs = data['seq'].to_list()
            drifts = [self.drift(seq=seq, raw=True) for seq in drifted_seqs]
            return DriftStats(drifts, monitor=self)
        return data if not raw else data.to_dict(orient='records')

    def combine_snapshots(self, snapshots):
        # combine snapshots into a single snapshot
        # -- snapshots is a dict or list of snapshots, each snapshot is a dict
        # -- each snapshot has a 'stats' and 'info' key
        # -- combine the stats and info into a single snapshot
        result = {}
        stats = result.setdefault('stats', {})
        info = result.setdefault('info', {})
        as_list = lambda s: s.values() if isinstance(s, dict) else s
        for snapshot in as_list(snapshots):
            if snapshot is None:
                continue
            stats.update(snapshot.get('stats', {}))
            info.update(snapshot.get('info', {}))
        return result

    def _assert_dataframe(self, dataset, rename=None, **query):
        def _ensure_dataframe(df):
            if isinstance(df, (list, np.ndarray, pd.Series)):
                df = pd.DataFrame(df)
                df.columns = [str(col) for col in
                              df.columns]  # ensure column names are strings (needed for json storage)
            assert isinstance(df, pd.DataFrame), f'dataset {dataset!r} cannot be processed as a DataFrame'
            return df

        if isinstance(dataset, (list, np.ndarray, pd.DataFrame, pd.Series)):
            df = _ensure_dataframe(dataset)
            query = query.get('query')
            if query:
                df = df.query(query) if isinstance(query, str) else df[query]
        elif isinstance(dataset, str):
            df = _ensure_dataframe(self.store.get(dataset, **query))
        else:
            df = _ensure_dataframe(dataset)
        assert len(df), f'dataset {dataset}, using query {query}, is empty, cannot take a snapshot'
        if rename:
            df.columns = [rename.get(col, col) for col in df.columns]
        return df
