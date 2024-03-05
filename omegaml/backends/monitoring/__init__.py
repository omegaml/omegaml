from itertools import product, pairwise

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from scipy.stats import ks_2samp, chisquare, wasserstein_distance
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

    def wasserstein_distance(self, d1, d2, ci=.95):
        # Wasserstein distance between two distributions
        # -- H0: d1, d2 are from the same distribution (=> no drift)
        # -- H1: alternative (=> drift)
        # -- H0 is rejected if pvalue < 1 - ci (default: 0.05)
        # https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wasserstein_distance.html
        result = wasserstein_distance(d1, d2)
        is_drift = result > ci
        return {
            'metric': result,
            'drift': is_drift,
            'pvalue': None,
            'location': None,
        }

    def sample_from_hist(self, hist, edges, n=100):
        probs = hist / np.sum(hist)
        return np.random.choice(np.linspace(edges[0], edges[-1], len(edges) - 1), n, p=probs)


class DriftStats:
    def __init__(self, data, monitor=None):
        self.drifts = data
        self.monitor = monitor
        self._df = None

    @property
    def df(self):
        if self._df is None:
            self._df = self.as_dataframe(self.drifts)
        return self._df

    @property
    def features(self):
        return self.df['column'].unique()

    @property
    def columns(self):
        return self.features

    @property
    def stats(self):
        return self.df.groupby('column')['statistic'].unique()

    def seq(self, column=None, statistic=None):
        df = self[column, statistic]
        return df['seq_from'].min(), df['seq_to'].max()

    def describe(self, column=None, statistic=None, percentiles=None, **query):
        df = self.as_dataframe(self.drifts, column=column, statistic=statistic, **query)
        return df.groupby(['column', 'statistic'])[['metric', 'pvalue']].describe(percentiles=percentiles).fillna(
            0).round(2)

    def drifted(self, column=None, statistic=None, summary=False, details=False, **query):
        df = self.as_dataframe(self.drifts, column=column, statistic=statistic, **query)
        if summary:
            return (df.groupby(['kind'])['drift'].sum() > 0).to_dict()
        flt = df['drift'] == True
        return df[flt]['drift'].sum() > 0 if not details else df[flt]

    def __getitem__(self, column):
        df = self.df
        column, statistic, *seq = column if isinstance(column, (list, tuple)) else (column, None)
        seq_from, seq_to = self._expand_seq(seq, default='baseline', column=column, statistic=statistic) if seq else (None, None)
        flt = df['column'] == column if column else (df.index == df.index)
        flt &= df['statistic'] == statistic if statistic else True
        flt &= df['seq_from'] == seq_from if seq_from is not None else True
        flt &= df['seq_to'] == seq_to if seq_to is not None else True
        return df[flt]

    def plot(self, column=None, statistic=None, seq=None, kind='dist', ax=None, **kwargs):
        statistic = statistic or 'mean'
        seq = seq or self.seq(column=column, statistic=statistic)
        if column:
            return self._plot_column(column, statistic, seq, kind, ax, **kwargs)
        return self._plot_all(statistic, seq, kind, ax, **kwargs)

    def _plot_column(self, column, statistic, seq, kind, ax, **kwargs):
        s1, s2 = seq if isinstance(seq, (list, tuple)) else [seq, seq]
        baseline_df = self[column, statistic, (s1, None)]
        target_df = self[column, statistic, (None, s2)]
        baseline = baseline_df['baseline'].iloc[0]
        target = target_df['target'].iloc[0]
        dt1 = baseline_df['dt_from'].iloc[0]
        dt2 = target_df['dt_to'].iloc[0]
        if kind == 'dist':
            ax = self._plot_dist(column, statistic, s1, s2, baseline, target, dt1, dt2, ax, **kwargs)
        elif kind == 'line':
            ax = self._plot_timeline(column, statistic, s1, s2, baseline, target, dt1, dt2, ax, **kwargs)
        return ax

    def _plot_all(self, statistic, seq, kind, ax, **kwargs):
        return self.as_dataframe(statistic=statistic).plot.bar('column', 'metric')

    def _plot_dist(self, column, statistic, s1, s2, baseline, target, dt1, dt2, ax, **kwargs):
        # prepare drift message
        drift_ind = 'detected' if self[column, statistic]['drift'].sum() > 0 else 'not detected'
        drift_stats = self[column, statistic, (None, s2)].iloc[0]['stats']
        drift_pvalue = self[column, statistic, (None, s2)].iloc[0]['pvalue']
        drift_msg = ", ".join((f'P={drift_pvalue:.3f}', f'{drift_stats}'))
        drift_text = f'{drift_ind} ({drift_msg})'
        # plot feature distribution
        for period in (baseline, target):
            if 'hist' in period:
                counts, edges = period['hist']
                print(counts, edges)
                ax = plt.stairs(counts, edges, fill=True, alpha=.8, **kwargs)
            if 'groups' in period:
                ax = plt.bar(period['groups'].keys(), period['groups'].values(), **kwargs)
        if ax:
            plt.suptitle(f'{column} distribution')
            plt.title(f'Drift {drift_text}\nBaseline: {dt1} Target: {dt2}', fontsize=8)
            plt.xlabel(column)
            plt.legend(['baseline', 'target'])
        return ax

    def _plot_timeline(self, column, statistic, s1, s2, baseline, target, dt1, dt2, ax, **kwargs):
        from matplotlib.dates import DateFormatter
        date_form = DateFormatter("%Y-%m-%d")
        df = self.df
        flt = df['column'] == column
        flt &= df['statistic'] == statistic
        dff = df[flt]
        dfx = (dff
               .pivot_table(index='seq_from',
                            columns='column',
                            values='metric')
               )
        ax = dfx.plot.line(style='-', marker='X')
        if ax:
            drift_text = 'detected' if dff['drift'].sum() > 0 else 'not detected'
            plt.suptitle(f'{column} distribution')
            plt.title(f'Drift {drift_text}\nBaseline: {dt1} Target: {dt2}', fontsize=8)
            #plt.xlabel('seq_from')
        return ax

    def _expand_seq(self, seq, default=None, column=None, statistic=None):
        if isinstance(seq, (list, tuple)):
            if len(seq) and isinstance(seq[0], (list, tuple)):
                seq_from, seq_to = seq[0]
            elif len(seq) and default == 'baseline':
                seq_from, seq_to = seq[0], None
            elif len(seq) and default == 'target':
                seq_from, seq_to = None, seq[0]
            else:
                seq_from, seq_to = None, None
        elif default == 'baseline':
            seq_from, seq_to = seq, None
        elif default == 'target':
            seq_from, seq_to = None, seq
        else:
            seq_from, seq_to = seq, seq
        seq_min, seq_max = self.seq(column=column, statistic=statistic)
        seq_from = seq_from if seq_from is None or seq_from >= 0 else (seq_max + seq_from)
        seq_to = seq_to if seq_to is None or seq_to >= 0 else (seq_max + seq_to + 1)
        seq_to = seq_to if int(seq_to or 0) > int(seq_from or 0) else None
        return seq_from, seq_to

    def baseline(self, column, statistic, seq=None):
        return self[column, statistic, (seq, None)]['baseline']

    def target(self, column, statistic, seq=None):
        return self[column, statistic, (None, seq)]

    def as_dataframe(self, drift_data=None, **query):
        drift = drift_data or self.drifts

        if isinstance(drift, list):
            return self._filter_df(pd.concat([self.as_dataframe(d) for d in drift]), **query)

        info = drift['info']
        stats = drift['stats']

        def drift_records(stats):
            for column in stats:
                for stat, values in stats[column].items():
                    yield {
                        'column': column,
                        'statistic': stat,
                        'drift': values['drift'],
                        'metric': values['metric'],
                        'pvalue': values.get('pvalue'),
                        'stats': ','.join(values.get('stats', [stat])),
                        'kind': info['baseline']['info']['kind'],
                        'dt_from': pd.to_datetime(info['dt_from']),
                        'dt_to': pd.to_datetime(info['dt_to']),
                        'seq_from': info['seq'][0],
                        'seq_to': info['seq'][1],
                        'baseline': info['baseline']['stats'][column],
                        'target': info['target']['stats'][column],
                    }

        return self._filter_df(pd.DataFrame(drift_records(stats)), **query)

    def _filter_df(self, df, **criterias):
        filters = {}
        for column, criteria in criterias.items():
            if criteria:
                criteria = list(criteria) if isinstance(criteria, (list, tuple)) else [criteria]
                filters[column] = df[column].isin(criteria)
        flt = None
        for column, colflt in filters.items():
            flt = (flt & colflt) if flt is not None else colflt
        return df[flt] if flt is not None else df


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
            snapshots = self.data()
            if snapshots is None:
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
        return len(self.data() or [])

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
            stats[s_col] = {
                'dtype': str(df1.dtypes[col]),
                'hist': np.histogram(values, bins=bins, density=False)
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
            samples = 100 if len(e1) < 100 else 1000
            d1 = calc.sample_from_hist(h1, e1, n=samples)
            d2 = calc.sample_from_hist(h2, e2, n=samples)
            metrics[col] = {
                # KS statistic, p_value
                # https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ks_2samp.html
                'ks': calc.ks_2samp(d1, d2, ci=ci),
                'wasserstein': calc.wasserstein_distance(d1, d2, ci=ci),
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
    def __init__(self, name, dataset=None, store=None, query=None, tracking=None, **kwargs):
        super().__init__(name, resource=dataset, store=store, query=query,
                         tracking=tracking, **kwargs)

    def snapshot(self, dataset=None, chunksize=None, columns=None, _prefix=None, kind='data', **query):
        """
        Take a snapshot of a dataset and log its feature distribution for later drift detection

        Args:
            dataset (str|pd.DataFrame|np.ndarray): the dataset to snapshot
            chunksize (int): the chunksize to use for reading the dataset
            columns (list): the columns to snapshot, defaults to all columns
            query (str|kwargs): additional query parameters to use when reading the dataset.
               If the dataset is a DataFrame, this is passed to df.query(); if the dataset is a
               stored resource, this is passed as store.get(, **query)

        Returns:
            dict: the snapshot
        """
        # TODO: for chunksizes need to combine hist for multiple chunks
        # -- https://stackoverflow.com/a/57884457/890242
        dataset = dataset if dataset is not None else self._resource
        query = query or self._query
        if isinstance(dataset, pd.DataFrame):
            df = dataset
            query = query.get('query')
            if query:
                df = df.query(query) if isinstance(query, str) else df[query]
        else:
            df = self.store.get(dataset, **query)
            if isinstance(df, np.ndarray):
                df = pd.DataFrame(df)
                df.columns = [str(col) for col in
                              df.columns]  # ensure column names are strings (needed for json storage)
        snapshot = self._do_snapshot(df, columns=columns, name=str(dataset), kind=kind, _prefix=_prefix)
        return snapshot


class ModelMonitor(DriftMonitorBase):
    def __init__(self, name, model=None, tracking=None, store=None):
        super().__init__(name, resource=model, store=store, tracking=tracking)

    def snapshot(self, model=None, X=None, Y=None, run=None):
        # what do we snapshot?
        # - validation metric (accuracy, f1, f2, confusion matrix etc)
        # - data input distribution (i.e. training/validation X)
        # - (expected) label distribution (Y)
        # NEXT:
        # - track labels (Y)
        # - track inputs (X)
        # - metrics, Y and X should also be possible to override via kwargs (instead of taking from tracking)
        model = model or self._resource
        run = run or 'all'
        snapshots = {}
        x_mon, y_mon = self._xy_monitor(model)
        if X is not None:
            snapshots['X'] = x_mon.snapshot(X, _prefix='X', kind='feature')
        if Y is not None:
            snapshots['Y'] = y_mon.snapshot(Y, _prefix='Y', kind='label')
        # return snapshot as expected
        # -- if no X or Y, return model snapshot
        # -- if X or Y, return X or Y snapshot
        # -- else return all snapshots as a dict(model=, X=, Y=)
        if self.tracking is not None:
            snapshots['model'] = self._snapshot_model(model, run=run)
        if X is None and Y is None:
            result = snapshots.get('model')
        elif X is not None and Y is None:
            result = snapshots.get('X')
        elif Y is not None and X is None:
            result = snapshots.get('Y')
        else:
            result = snapshots
        return result

    def _xy_monitor(self, model):
        x_mon = DataDriftMonitor(f'{model}_X', store=self.store, tracking=self.tracking)
        y_mon = DataDriftMonitor(f'{model}_Y', store=self.store, tracking=self.tracking)
        return x_mon, y_mon

    def _snapshot_model(self, model, run):
        df: pd.DataFrame = self.tracking.data(run=run, event='metric')
        assert not df.empty, f"could not find any metrics for model in {self.tracking=} {run=}"
        index_cols = ['experiment', 'run', 'step', 'dt']
        key_cols = ['key']
        value_cols = ['value']
        # - reshape from long to wide format
        df = (pd.pivot_table(df.fillna(1),
                             index=index_cols,
                             columns=key_cols,
                             values=value_cols,
                             dropna=True)
              .droplevel(0, axis=1)
              .reset_index())
        mon_columns = list(set(df.columns) - set(index_cols + key_cols))
        ensure_list = lambda v: v if isinstance(v, (list, tuple)) else list(v) if isinstance(v, range) else [v]
        snapshot = self._do_snapshot(df, columns=mon_columns, name=str(model), kind='model',
                                     info={'run': ensure_list(run)})
        return snapshot

    def drift(self, seq=None, d1=None, d2=None, ci=.95, raw=False):
        model_drift = super().drift(seq=seq, d1=d1, d2=d2, ci=ci, raw=True)
        x_mon, y_mon = self._xy_monitor(self._resource)
        x_drift = x_mon.drift(seq=seq, d1=d1, d2=d2, ci=ci, raw=True)
        y_drift = y_mon.drift(seq=seq, d1=d1, d2=d2, ci=ci, raw=True)
        drifts = []
        for s_drift in (model_drift, x_drift, y_drift):
            if isinstance(s_drift, list):
                drifts.extend(s_drift)
            elif s_drift is not None:
                drifts.append(s_drift)
        drifts = drifts[0] if len(drifts) == 1 else drifts
        return drifts if raw else DriftStats(drifts)

    def clear(self):
        super().clear()
        x_mon, y_mon = self._xy_monitor(self._resource)
        x_mon.clear()
        y_mon.clear()

    def _calc_model_drift(self):
        # what do we measure
        # - metric: we measure a drift in metric/confusion matrix
        # - X: measure drift in input data, where some sequence of recent predict() input data is taken as d2
        # - Y: measure drift in output, where some sequence of recent predict() output is taken as d2
        # - is confusion matrix like a category or a numeric.var? (e.g. each value in cm is a category?, each value in cm is a )
        pass
