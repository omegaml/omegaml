import numpy as np
import pandas as pd
import warnings
from datetime import datetime
from itertools import pairwise, product

from omegaml.backends.monitoring.alerting import AlertRule
from omegaml.backends.monitoring.stats import DriftStats, DriftStatsCalc
from omegaml.util import dict_merge, tryOr


class DriftMonitorBase:
    def __init__(self, resource=None, store=None, query=None, tracking=None, kind=None,
                 statscalc=None, **kwargs):
        self.store = store
        self._resource = resource
        self._query = query or kwargs
        self._kind = kind
        self._data = None
        self._statscalc = statscalc or DriftStatsCalc()
        self.tracking = tracking
        self.samples = [100, 1000]  # small and large sample sizes
        self.max_corr_columns = 50  # maximum number of columns for correlation calculation = 50

    def __repr__(self):
        return f'{self.__class__.__name__}({self._resource})'

    @property
    def df(self):
        return pd.json_normalize(self.data)

    def snapshot(self, *args, **kwargs):
        """ take a snapshot of the data

        This method is called by a monitor job to take a snapshot of the data to monitor.
        The specific implementation is subject to the monitor type, e.g. a DataDriftMonitor
        """
        raise NotImplementedError

    def summary(self, seq=None, d1=None, d2=None, ci=.95, raw=False, column=None, statistic=None):
        """ Calculate and summarize drift statistics

        This effectively calls DriftMonitor.compare() and DriftStats.summary() on the
        drift statistics

        Args:
            seq (list|str): a list of snapshot indices to compare in the format [i, j],
               or one of 'baseline', 'series'. Use 'baseline' to compare every snapshot
               to the first snapshot, or 'series' to compare each snapshot to the previous.
               [i, j] are 0-indexed snapshot indices, can be specified as negative indices
               to indicate the last n-th snapshot.
            d1 (int): the first snapshot index to compare, optional
            d2 (int): the second snapshot index to compare, optional
            ci (float): the confidence interval for the drift test, defaults to .95
            raw (bool): if True, returns drift statistics as a dict, otherwise
                returns a DriftStats instance
            column (str): the column to summarize, optional
            statistic (str): the statistic to summarize, optional

        Returns:
            DriftStats|[dict]: a drift statistics instance (if raw=False), or a list of dicts

        See Also:
            - DriftStats.summary for details
        """
        seq = seq or 'baseline'
        stats = self.compare(seq=seq, d1=d1, d2=d2, ci=ci, raw=raw)
        return stats if raw else stats.summary(column=column, statistic=statistic)

    def compare(self, seq=None, d1=None, d2=None, ci=.95, baseline=0, raw=False, matcher=None, since=None):
        """ calculate drift

        Args:
            seq (list|str): a list of snapshot indices to compare in the format [i, i+1, ..., i+n],
               or one of 'recent', 'baseline', 'series'. Use 'baseline' to compare every snapshot
               to the first snapshot, or 'series' to compare each snapshot to the previous, or
               'recent' to compare the most recent snapshot to the one preceeding. [i, j] are 0-indexed
               snapshot indices, can be specified as negative indices to indicate the last n-th snapshot.
               Defaults to 'recent', which is the same as [-2, -1].
            d1 (pd.DataFrame): the first dataset to compare, optional. If specified d2 must also be specified.
               A snapshot is taken from the data before comparing. Use seq=None to compare d1 and d2 directly.
            d2 (pd.DataFrame): the second dataset to compare, optional. If specified d1 must also be specified.
                A snapshot is taken from the data before comparing. Use seq=None to compare d1 and d2 directly.
            ci (float): the confidence interval for the drift test, defaults to .95
            baseline (int): the baseline snapshot index to compare to, defaults to 0
            since (datetime|str): only consider snapshots since this date. If type(str), must
                be an ISO8601 formatted date string or 'last'. For 'last', the last snapshot's
                'since' value is used, and if not present, the previous snapshot's dt is used.
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
        if seq in (None, 'recent'):
            seq = [-2, -1]
            drifts = [self._calculate_drift(seq=seq, d1=d1, d2=d2, ci=ci, raw=True, matcher=matcher, since=since)]
        elif isinstance(seq, (list, tuple)) and len(seq) > 1:
            # [0, 1, 2, ...] => compare each snapshot to the previous
            drifts = [self._calculate_drift(seq=[i, j], ci=ci, raw=True, since=since) for i, j in pairwise(seq)]
        elif seq == 'series':
            # [0, 1, 2, ...] => compare each snapshot to the previous
            seq = range(0, len(self))
            drifts = [self._calculate_drift(seq=[i, j], ci=ci, raw=True, since=since) for i, j in pairwise(seq)]
        elif seq == 'baseline':
            # [0, 1], [0, 2], [0, 3], ... => compare each snapshot to the baseline
            seq = list(product([baseline], range(1, len(self))))
            drifts = [self._calculate_drift(seq=pair, ci=ci, raw=True, since=since) for pair in seq]
        else:
            raise ValueError(
                f'invalid drift sequence {seq}, must be "recent", "baseline", "series" or a list of snapshot indices.')
        # filter out empty drifts
        drifts = [d for d in drifts if d]
        return DriftStats(drifts, monitor=self) if not raw else drifts

    def _calculate_drift(self, seq=None, d1=None, d2=None, ci=.95, raw=False, matcher=None, since=None):
        # return a single drift
        # -- to calculate a drift history, call this method multiple times for different seq
        since = since.isoformat() if isinstance(since, datetime) else since
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
        if since == 'last':
            # align with last snapshots's period
            # -- rationale: upon mon.snapshot(since='last') a new snapshot is taken
            #               according to the previous most recent snapshot's dt. This
            #               value is stored as the 'since' value in the snapshot['info'].
            #               Thus upon since=='last' we align the drift calculation with
            #               the last snapshot's 'since' period, assuming previous drifts are
            #               already calculated or not of interest.
            since = snapshots[-1]['info'].get('since') or snapshots[seq[0]]['info']['dt']
        in_range = not since or s2['info']['dt'] >= since
        if in_range:
            # we only check s2 because for any (s2 is newer than s1), drift calculation is necessary
            drift = self._calc_drift(s1, s2, ci=ci, matcher=matcher)
            eff_seq = lambda s: s if s >= 0 else len(snapshots) + s
            drift['info']['seq'] = [eff_seq(seq[0]), eff_seq(seq[1])]
        else:
            # drift calculation is not necessary, return empty stats
            drift = []
        return DriftStats(drift, monitor=self) if not raw else drift

    @property
    def dataset(self):
        return f'.monitor/{self._resource}'

    @property
    def _drift_alert_key(self):
        return f'drift:{self._resource}'

    @property
    def statscalc(self):
        if not hasattr(self, '_statscalc'):
            self._statscalc = DriftStatsCalc()
        return self._statscalc

    @statscalc.setter
    def statscalc(self, value):
        self._statscalc = value
        if hasattr(self._statscalc, '_init_mixin'):
            self._statscalc._init_mixin()

    @property
    def data(self):
        self.refresh(**self._query)
        return self._data

    def refresh(self, run=None, since=None, **kwargs):
        run = run or self._query.get('run', '*')
        since = since or self._query.get('since')
        self._query.update(run=run, since=since)
        self._data = self._filter_data(**self._query)

    def _filter_data(self, run='all', event='snapshot', since=None):
        df = self.tracking.data(run=run, event=event, key=self._resource, kind=self._kind, since=since)
        return df['value'].to_list() if not df.empty else []

    def report(self, seq=None, format='html'):
        data = self.compare(seq=seq, raw=True)
        FORMATS = {
            'html': lambda v: pd.json_normalize(v).to_html(),
            'json': lambda v: pd.DataFrame(v).to_json(),
            'dict': lambda v: data if len(data) > 1 else data[0],
        }
        return FORMATS[format](data) if format in FORMATS else data

    def clear(self, force=False):
        """ clear all data associated with this monitor

        All data is removed from the experiment's dataset. This is not recoverable.

        Args:
            force (bool): if True, clears all data, otherwise raises an error

        Caution:
            * this will clear all experiment data and is not recoverable

        Raises:
            AssertionError: if force is not True
        """
        self.tracking.clear(force=force)

    def __len__(self):
        # make more efficient
        return len(self.data or [])

    def _snapshot_info(self, name, kind, dt=None, **kwargs):
        info = {
            'resource': name if isinstance(name, str) else str(type(name)),
            'kind': kind or self._kind,
            'dt': dt or datetime.utcnow().isoformat(),
        }
        info.update(kwargs)
        return info

    def _most_recent_snapshots(self, n=1):
        snapshots = self.data
        start = max(0, len(snapshots) - n)
        stop = len(snapshots)
        return snapshots[start:stop] if snapshots else []

    def _most_recent_snapshot_time(self, n=1):
        recent = self._most_recent_snapshots(n=n)
        return recent[0]['info']['dt'] if recent else datetime.min

    def _do_snapshot(self, df1: pd.DataFrame, columns=None, name=None, kind=None, info=None, prefix=None,
                     postfix=None, catcols=None, correlate=False):
        """ calculate a snapshot of the data

        This method calculates a snapshot for a DataFrame, including statistics and histograms or group frequencies
        for numeric and categorical columns, respectively. Use the _log_snapshot method to log the snapshot to
        the tracking system.

        Note this an internal method to calculate a single DataFrame snapshot. Use the monitor.snapshot() method to
        calculate a snapshot for the monitor's data. For example, a DataDriftMonitor would use this method directly
        to calculate the snapshots of two datasets to compare for drift. A ModelDriftMonitor would use this method
        multiple times to calculate the snapshot of the model's features (X), labels (Y) and metrics.

        Args:
            df1 (pd.DataFrame): the data to snapshot
            columns (list): the columns to snapshot, defaults to all columns
            name (str): the name of the snapshot
            kind (str): the kind of the snapshot
            info (dict): additional information to include in the snapshot
            prefix (str): the prefix to apply to all columns
            postfix (str): the postfix to apply to all columns
            catcols (list): the columns to treat as categorical
            correlate (bool|list): whether to calculate correlations, defaults to False. If a list of columns
                is specified, only those columns are correlated. If True, all numeric columns are correlated.

        Returns:
            dict: the snapshot, with the following keys:
                - stats (dict): the statistics of the snapshot
                    - '<numeric column>' (dict): the statistics for column X
                        * 'dtype' (str): the data type of the column
                        * 'hist' (tuple): the histogram of the column, (frequencies, edges)
                        * 'std' (float): the standard deviation of the column
                        * 'mean' (float): the mean of the column
                        * 'min' (float): the minimum value of the column
                        * 'max' (float): the maximum value of the column
                        * 'percentiles' (list): the percentiles of the column
                        * 'corr' (dict): the correlations respective to other columns,
                             with keys 'pearson', 'spearman'. This is the result of calling
                                df.corr(method=method) for the column, where method is either
                                'pearson' or 'spearman. The result is a dict of column => correlation.
                                This value can be None if the number of columns is too large or an error occured
                                during calculation.
                    - '<categorical column>' (dict): the statistics for column X
                        * 'dtype' (str): the data type of the column
                        * 'groups' (dict): the group frequencies of the column
                            - '<group>' (str): the group name
                            - '<count>' (int): the group frequency
                - info (dict): the meta information of the snapshot
                    - resource (str): the resource name
                    - kind (str): the kind of the snapshot
                    - dt (str): the datetime of the snapshot
                    - len (int): the number of rows in the snapshot
                    - num_columns (list): the numeric columns in the snapshot
                    - cat_columns (list): the categorical columns in the snapshot
        """
        # prepare info
        extra_info = info or {}
        df1 = df1[columns] if columns else df1
        catcols = [c for c in catcols if c in df1.columns] if catcols else []
        numeric_columns = list(set(df1.select_dtypes(include='number').columns) - set(catcols))
        cat_columns = list(set(df1.columns) - set(numeric_columns))
        snapshot = {}
        extra_info.update({
            'len': len(df1),
        })
        stats = snapshot.setdefault('stats', {})
        info = snapshot.setdefault('info', self._snapshot_info(name, kind, **extra_info))
        prefixed = lambda col: f'{prefix}_{col}' if prefix else col
        postfixed = lambda col: f'{col}_{postfix}' if postfix else col
        pre_or_post_fixed = lambda col: (postfixed(prefixed(col)) if isinstance(col, str)
                                         else [postfixed(prefixed(c)) for c in col])
        info['num_columns'] = pre_or_post_fixed(numeric_columns)
        info['cat_columns'] = pre_or_post_fixed(cat_columns)
        # calculate numeric statistics
        # -- correlations
        correlations = {}
        corr_limits = len(numeric_columns) <= self.max_corr_columns
        corr_columns = correlate if isinstance(correlate, (list, tuple)) else numeric_columns
        if correlate and corr_limits:
            # calculating correlations is computationally expensive
            # -- we only calculate correlations if the number of columns is below a threshold
            for method in ['pearson', 'spearman']:
                try:
                    correlations[method] = df1[corr_columns].corr(method=method).to_dict()
                except:
                    correlations[method] = None
        else:
            if not corr_limits:
                warnings.warn(f'too many columns for correlation calculation, max columns = {self.max_corr_columns}')
            for method in ['pearson', 'spearman']:
                correlations[method] = None
        # -- summary statistics
        for col in numeric_columns:
            s_col = pre_or_post_fixed(col)
            values = df1[col].dropna().values
            bins = 10 if len(values) < 1000 else 100
            probs = [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, .95]
            stats[s_col] = {
                'dtype': str(df1.dtypes[col]),
                'probs': probs,
                'bins': bins,
                'hist': np.histogram(values, bins=bins, density=False),
                'pdf': np.histogram(values, bins=bins, density=True),
                'std': np.std(values),
                'var': np.var(values),
                'mean': np.mean(values),
                'median': np.median(values),
                'min': np.min(values),
                'max': np.max(values),
                'percentiles': [np.quantile(values, probs), probs],
                'corr': {method: tryOr(lambda: correlations[method][col], None)
                         for method in correlations},
                'missing': len(df1) - len(values),
            }
        # calculate categorical statistics
        for col in cat_columns:
            s_col = pre_or_post_fixed(col)
            stats[s_col] = {
                'dtype': str(df1.dtypes[col]),
                'groups': df1[col].value_counts().to_dict(),
                'pmf': df1[col].value_counts(normalize=True).to_dict(),
                'missing': len(df1) - len(df1[col].dropna()),
            }
        return snapshot

    def _log_snapshot(self, snapshot):
        self.tracking.use()  # ensure we have an active run
        self.tracking.log_event('snapshot', self._resource, snapshot, kind=snapshot['info']['kind'])

    def _log_drift(self, drift, **extra):
        self.tracking.use()  # ensure we have an active run
        self.tracking.log_event('drift', self._resource, drift, **extra)

    def _calc_drift(self, s1, s2, ci=.95, matcher=None):
        """ calculate drift between two snapshots

        Args:
            s1 (dict): the first snapshot, see DriftMonitor.snapshot()
            s2 (dict): the second snapshot, see DriftMonitor.snapshot()
            ci (float): the confidence interval for the drift test, defaults to .95
            matcher (dict): a dict that maps columns 'old' => 'new', e.g. {'Y_y': 'Y_0'}.
               this is useful to map columns from one snapshot to another, e.g. when
               column names change between snapshots. Pass as dict(d1={...}, d2={...})
               to specifically map columns for the first and second snapshot. By default
               columns present in d1 but missing in d2 are auto-matched by position.

        Returns:
            dict: the drift statistics, with keys 'info', 'stats', 'sample', 'result'
                * 'info' (dict): meta information about the drift
                    - 'dt_from' (str): the datetime of the first snapshot
                    - 'dt_to' (str): the datetime of the second snapshot
                    - 'ci' (float): the confidence interval for the drift test
                    - 'baseline' (dict): the first snapshot
                    - 'target' (dict): the second snapshot
                    - 'columns_map' (dict): the column name matcher, if any,
                        e.g. {'Y_y': 'Y_0'}, mapping column Y_y to Y_0
                * 'stats' (dict): the drift statistics per column
                    - '<numeric column>' (dict): the drift statistics for column X
                        * 'ks' (tuple): the KS statistic and p-value
                        * 'wasserstein' (float): the Wasserstein distance
                        * 'mean' (dict): the mean drift statistics
                            - 'metric' (float): the mean drift metric
                            - 'score' (float): the mean drift score
                            - 'stats' (list): the columns that drifted
                            - 'drift' (bool): True if drift was detected, False otherwise
                    - '<categorical column>' (dict): the drift statistics for column X
                        * 'chisq' (tuple): the chi-square statistic and p-value
                        * 'mean' (dict): the mean drift statistics
                            - 'metric' (float): the mean drift metric
                            - 'score' (float): the mean drift score
                            - 'stats' (list): the columns that drifted
                            - 'drift' (bool): True if drift was detected, False otherwise
                * 'sample' (dict): the sampled data for each column
                    - 'd1' (list): the sampled data from s1
                    - 'd2' (list): the sampled data from s2
                * 'result' (dict): the drift summary
                    - 'drift' (bool): True if drift was detected, False otherwise
                    - 'method' (str): the method used to calculate drift
                    - 'metric' (float): the drift metric, 0 = no drift, > 0 = drift
                    - 'columns' (list): the columns that drifted
        """
        calc = self.statscalc
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
            # -- hist[0] is the frequencies for each bin
            # -- hist[1] is the bin edges
            h1, e1 = s1['stats'][_c('d1', s1, col)]['hist']
            h2, e2 = s2['stats'][_c('d2', s2, col)]['hist']
            sd = s1['stats'][_c(None, s1, col)]['std']
            samples = self.samples[0] if len(e1) < 100 else self.samples[1]
            d1 = calc.sample_from_hist(h1, e1, n=samples)
            d2 = calc.sample_from_hist(h2, e2, n=samples)
            cdf1 = calc.cdf_from_hist(h1, e1)
            cdf2 = calc.cdf_from_hist(h2, e2)
            metrics.setdefault(col, {})
            for metric, metric_fn in calc.metrics('numeric').items():
                metrics[col][metric] = tryOr(lambda: metric_fn(d1, d2, ci=ci, sd=sd),
                                             {'score': 0, 'drift': False, 'metric': None, 'error': True})
            sample[col] = {
                'd1': d1,
                'd2': d2,
            }
        for col in cat_columns:
            g1 = s1['stats'][_c('d1', s1, col)]['groups']
            g2 = s2['stats'][_c('d2', s2, col)]['groups']
            # calculate normalized group frequencies (%), required for statistic test
            g1v = np.array(list(g1.values()))
            g2v = np.array(list(g2.get(g, 0) for g in g1))
            d1 = (np.array(g1v) / np.sum(g1v)).round(decimals=99)
            d2 = (np.array(g2v) / np.sum(g2v)).round(decimals=99)
            metrics.setdefault(col, {})
            for metric, metric_fn in calc.metrics('categorical').items():
                metrics[col][metric] = tryOr(lambda: metric_fn(d1, d2, ci=ci, sd=sd),
                                             {'score': 0, 'drift': False, 'metric': None, 'error': True})
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
        # -- drift is detected if the mean of the drift statistics is > 0.5
        # -- we use the following metrics to calculate drift:
        #    - ks: Kolmogorov-Smirnov test for goodness of fit
        #    - wasserstein: Wasserstein distance
        #    - chisq: chi-square test for goodness of fit
        # rationale for not using jsd, kld, hellinger, bhattacharyya: these metrics are not symmetric
        mean_metrics = calc.mean_metrics
        for col in numeric_columns + cat_columns:
            col_stats = metrics[col]
            mean_stats = {}
            mean_stats['metric'] = np.mean([v['score'] for k, v in col_stats.items() if v if k in mean_metrics])
            mean_stats['score'] = np.mean([v['score'] for k, v in col_stats.items() if v if k in mean_metrics])
            mean_stats['stats'] = [k for k, v in col_stats.items() if v.get('drift') if k in mean_metrics]
            mean_stats['drift'] = mean_stats['metric'] > 0.5
            col_stats['mean'] = mean_stats
        # per dataset
        column_drifts = [v['mean']['drift'] for v in metrics.values()]
        column_scores = [v['mean']['score'] for v in metrics.values()]
        result['drift'] = any(column_drifts)
        result['method'] = 'mean'
        result['score'] = np.mean(column_drifts)
        result['metric'] = np.mean(column_scores)
        result['columns'] = [col for col in numeric_columns + cat_columns if metrics[col]['mean']['drift']]
        return drift

    def _notify_alerts(self, alerts=None, notify=True):
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

    def capture(self, column=None, statistic=None, rules=None, seq='baseline', since=None, baseline=0):
        """
        capture detected drift, if any, by logging an event in tracking

        This method is called by a monitor job to log a drift event in
        the tracking system. It logs a 'drift' event with the resource name
        as the event key, and the drift indicator as the event value. Extra
        information is logged to link back to the monitoring system, such as
        the monitor name, the sequence number and the column that drifted.

        To retrieve the drift events, use the tracking system to query for
        events of type 'drift' and the resource name as the event key::

            event = tracking.data(event='drift', key='resource_name')

        The event['value'] is a dict with the drift indicators, of the following
        format:

           {'columns': {'X_0': True},
            'info': {
               'feature': ['X_0'], # the feature that drifted
               'seq': [[0, 1]]}, # the sequence that drifted
            'summary': {'feature': True}} # the summary of the drift

        * `columns` is a dict of columns that drifted, with the column name as key
        * `info` is a dict with additional information about the drift, in particular
            * `feature` is a list of features that drifted (ModelMonitor)
            * `label` is a list of labels that drifted (ModelMonitor)
            * `data` is a list of data columns that drifted (DataMonitor)
            * `seq` is the sequence number that drifted (all monitors)
        * `summary` is a dict with a summary of the drift, with each kind of drift
            listed (e.g. 'feature', 'label', 'data')

        Args:
            column (str): the column that drifted, optional
            statistic (str): the statistic that drifted, optional
            rules (list): a list of alert rules to apply, optional
            seq (str): the sequence to compare to, defaults to 'baseline'
            baseline (int): the baseline sequence to compare to, defaults to 0

        Returns:
            bool: True if drift was detected and logged, False otherwise
        """
        stats = self.compare(seq=seq, baseline=baseline, since=since)
        summary = stats.summary(column=column, statistic=statistic, raw=True)
        if summary['info']['seq']:
            self._log_drift(summary, monitor=self._resource)
            self._notify_alerts(rules)
            return True
        return False

    def _make_alert_rules(self, alerts):
        # ensure we have a list of AlertRule instances
        rules = []
        for alert in alerts:
            rule = AlertRule(monitor=self, **alert) if not isinstance(alert, AlertRule) else alert
            rules.append(rule)
        return rules

    def events(self, event='drift', column=None, statistic=None, run=None, since=None, stats=True, raw=False):
        """
        Retrieve drift events

        Args:
            event (str): the events to retrieve, either 'drift', 'alert', 'snapshot', defaults to 'drift'
            column (str): the column to retrieve drift events for, defaults to all columns
            statistic (str): the statistic to retrieve drift events for, defaults to all statistics.
              This is ignored for events 'alert', 'snapshot'.
            run (int|str): the run to query, defaults to all runs
            since (datetime|str): only consider events since this date. If type(str), must
                be an ISO8601 formatted date string.
            stats (bool): if True, return a DriftStats instance, defaults to True
            raw (bool): if True, return raw event data, defaults to False

        Returns:
            pd.DataFrame|[dict]|DriftStats: the drift events as a DataFrame if raw=False,
              else a list of dicts. If stats=True, returns a DriftStats instance.
        """
        run = run or '*'
        column = column or '*'
        RETRIEVERS = {
            'drift': self._get_drift_events,
            'alert': self._get_alert_events,
            'snapshot': lambda *args, **kwargs: self.refresh(**kwargs) or (self.df if not raw else self.data)
        }
        retriever = RETRIEVERS[event]
        return retriever(run=run, since=since, column=column, statistic=statistic, stats=stats, raw=raw)

    def _get_drift_events(self, run=None, since=None, column=None, statistic=None, stats=False, raw=False):
        data = self.tracking.data(run=run, event='drift', key=self._resource, since=since,
                                  column=column, statistic=statistic)
        if len(data) and stats:
            # -- each drift event is a list of drift indicators, see .capture()
            # -- 'seq' is the respective (min, max) sequence associated with the drift event
            # ==> drifted_seqs is the list of (min, max) sequence numbers to recalculate the drifts
            drifted_seqs = (data['value']  # all drift summaries
                            .apply(lambda v: v['info']['seq'])  # extract seqs
                            .explode()  # flatten seqs
                            .to_list())  # get a list of lists
            drifts = [self.compare(seq=seq, raw=True) for seq in drifted_seqs]
            return DriftStats(drifts, monitor=self)
        return data if not raw else data.to_dict(orient='records')

    def _get_alert_events(self, run=None, column=None, statistic=None, since=None, raw=False, stats=False):
        """ Retrieve drift alerts

        Args:
            run (int|str): the run to query, defaults to all runs
            column (str): the column to retrieve drift events for, defaults to all columns
              This is ignored for event='alert'.
            statistic (str): the statistic to retrieve drift events for, defaults to all statistics.
              This is ignored for event='alert'.
            since (datetime|str): only consider alerts since this date. If type(str), must
                be an ISO8601 formatted date string.
            raw (bool): if True, return raw alert data, defaults to False
            stats (bool): if True, return a DriftStats instance, defaults to False

        Returns:
            pd.DataFrame|[dict]|DriftStats: the alerts as a DataFrame if raw=False,
              else a list of dicts. If stats=True, returns a DriftStats instance.
        """
        run = run or '*'
        data = self.tracking.data(run=run, event='alert', key=self._drift_alert_key,
                                  since=since)
        if stats:
            # -- data['value'] is a series of dicts, each dict is a drift event
            # -- each drift event is a list of drift indicators, see .capture()
            # -- 'seq' is the respective (min, max) sequence associated with the drift event
            # ==> drifted_seqs is the list of (min, max) sequence numbers to recalculate the drifts
            drifted_seqs = (data['value']
                            .explode('value')  # get all events as a list
                            .apply(lambda v: v['value']['info']['seq'])  # get all seqs as a list of lists
                            .explode()  # get all seqs as a series
                            .to_list())  # get all seqs as a flattened list
            drifts = [self.compare(seq=seq, raw=True) for seq in drifted_seqs]
            return DriftStats(drifts, monitor=self) if not raw else drifts
        return data if not raw else data.to_dict(orient='records')

    def _combine_snapshots(self, snapshots):
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
            dict_merge(stats, snapshot.get('stats', {}))
            dict_merge(info, snapshot.get('info', {}))
        return result

    def _dataset_as_dataframe(self, dataset, rename=None, filter=None, **query):
        query = filter or query or self._query

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
