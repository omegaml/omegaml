import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from omegaml.util import ensure_list
from scipy.stats import ks_2samp, chisquare, wasserstein_distance


class DriftStatsCalc:
    def ks_2samp(self, d1, d2, ci=.95):
        # two-sample Kolmogorov-Smirnov test for goodness of fit
        # -- H0: d1, d2 are from the same distribution (=> no drift)
        # -- H1: alternative (=> drift)
        # -- H0 is rejected if pvalue < 1 - ci (default: 0.05)
        # https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ks_2samp.html
        result = ks_2samp(d1, d2, method='asymp')
        score = self.calculate_score(result.statistic)
        is_drift = result.pvalue < (1 - ci)
        return {
            'metric': result.statistic,
            'score': score,
            'drift': is_drift,
            'pvalue': result.pvalue,
            'location': result.statistic_location,
        }

    def chisquare(self, d1, d2, ci=.99, sd=None):
        # one-way chi-square test
        # -- H0: categorical frequencies in d2 match the expectation in d1 (=> no drift)
        # -- H1: alterantive (=> drift)
        # -- H0 is rejected if pvalue < 1
        # https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chisquare.html#scipy.stats.chisquare
        result = chisquare(f_obs=d2, f_exp=d1)
        is_drift = result.pvalue < 1
        score = self.calculate_score(result.statistic)
        return {
            'metric': result.statistic,
            'score': score,
            'drift': is_drift,
            'pvalue': result.pvalue,
            'location': None,
        }

    def wasserstein_distance(self, d1, d2, ci=.95, sd=None):
        # Wasserstein distance between two distributions
        # calculates a normalized distance between two distributions
        # -- normalized by the standard deviation of d1
        # -- H0: d1, d2 are from the same distribution (=> no drift)
        # -- H1: alternative (=> drift)
        # -- H0 is rejected if normalized distance is > (1 - ci) sd
        # https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wasserstein_distance.html
        sd = sd or np.std(d1, ddof=1)
        wd = wasserstein_distance(d1, d2)
        score = self.calculate_score(wd / sd)
        is_drift = (score > ci)
        return {
            'metric': wd,
            'score': score,
            'drift': is_drift,
            'pvalue': None,
            'location': None,
        }

    def sample_from_hist(self, hist, edges, n=100):
        n = 100 if n is True else n
        probs = hist / np.sum(hist)
        return np.random.choice(np.linspace(edges[0], edges[-1], len(edges) - 1), n, p=probs)

    def mean_std_from_hist(self, counts, bins):
        """ calculated the standard deviation from a histogram """
        # adopted from https://stackoverflow.com/a/57400289/890242
        mids = 0.5 * (bins[1:] + bins[:-1])
        probs = counts / np.sum(counts)
        mean = np.sum(probs * mids)
        sd = np.sqrt(np.sum(probs * (mids - mean) ** 2))
        return mean, sd

    def cdf_from_hist(self, counts, bins):
        """ calculate the estimated CDF from a histogram """
        # adopted from https://stackoverflow.com/a/74032972/890242
        cdf = np.cumsum(counts * np.diff(bins))
        return cdf

    def sigmoid(self, x):
        return 1 / (1 + np.exp(-x))

    def calculate_score(self, metric, pvalue=None, ci=.95, sd=None):
        # TODO need a better generic score
        return self.sigmoid(metric)


class DriftStats:
    def __init__(self, data, monitor=None):
        self.drifts = data
        self.monitor = monitor
        self._df = None

    def __repr__(self):
        return f'DriftStats({self.monitor},drifts={len(self.drifts)})'

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

    @property
    def data(self):
        return self.drifts

    def seq(self, column=None, statistic=None):
        df = self[column, statistic]
        return [df['seq_from'].min(), df['seq_to'].max()]

    def describe(self, column=None, statistic=None, percentiles=None, kind='drift', **query):
        df = self.as_dataframe(self.drifts, column=column, statistic=statistic, **query)
        if kind == 'drift':
            result = (df.groupby(['column', 'statistic'])[['metric', 'pvalue']]
                      .describe(percentiles=percentiles)
                      .fillna(0)
                      .round(2))
        else:
            return None
        return result

    def summary(self, column=None, statistic=None, raw=False, **query):
        """ describe drifted features

        Args:
            column (str): the column to filter by
            statistic (str): the statistic to filter by
            summary (bool): return a summary of drifted features
            raw (bool): return the raw drift statistics as a dict
            **query: additional query parameters

        Returns:
            result (pd.Series|dict|None): a summary of drifted features or the detailed drifts
                * if summary is True, returns a dict with the following keys:
                    - columns: a dict of columns (str) => drifted (bool)
                    - summary: a dict of kinds (str) => drifted (bool)
                    - info: a dict of kinds (str) => columns (list) and seqs with drift (list)

        Usage:
            stats = mon.compare()
            stats.summary() -- get a summary of drifted features
            =>
              # indicates a drift in data features, specifically column '0'
              {
               'columns': {'0': True},
               'summary': {'data': True},
               'info': {'data': ['0'], 'seq': [(0, 1)]}
              }

            The summary indicates that feature '0' has drifted in the 'data' kind. Other
            kinds include 'feature' and 'label', for model features and labels respectively,
            when DriftStats are created from a ModelMonitor. For a quick check if any drift has occurred,
            check the ['info']['seq'] list; if it is empty, no drift has been detected.

        See Also:
            * DriftMonitorBase.compare() for details on drift events, which are effectively logs
              of DriftStats.summary() results
        """
        df = self.as_dataframe(self.drifts, column=column, statistic=statistic, **query)
        if df.empty:
            result = {
                'columns': {},
                'summary': {},
                'info': {'seq': []},
            }
        else:
            # prepare summary
            drifted = df['drift'] == True
            drifted_seqs = (df[drifted][['seq_from', 'seq_to']]
                            .drop_duplicates()
                            .apply(lambda v: [v['seq_from'], v['seq_to']], axis=1)
                            .tolist())
            result = {
                'columns': (df.groupby('column')
                            ['drift'].sum() > 0).to_dict(),
                'summary': (df.groupby('kind')
                            ['drift'].sum() > 0).to_dict(),
                'info': (df.groupby('kind')
                         .apply(lambda v: list(v['column'].sort_values().unique()))
                         .to_dict()),
            }
            result['info']['seq'] = drifted_seqs
        if not raw:
            # convert summary to pd.DataFrame
            s = result
            col_by_kind = {col: kind for kind, cols in s['info'].items()
                           for col in cols if kind != 'seq'}
            df = pd.DataFrame({
                'column': s['columns'].keys(),
                'drift': s['columns'].values(),
            })
            df['kind'] = df['column'].apply(lambda v: col_by_kind.get(v))
            df['seq'] = pd.Series(s['info']['seq'] * len(df))
            result = df
        return result

    def __getitem__(self, spec):
        """
        Get drift statistics for a given column, statistic, seq_from, seq_to

        Args:
            spec (tuple): (column, statistic, seq_from, seq_to), or a subset therefor,
               e.g. (column,), (column, statistic), (column, statistic, seq_from),
                (column, statistic, seq_from, seq_to)

        Usage:
            stats['column'] -- get all statistics for a column
            stats['column', 'mean'] -- get mean statistics for a column
            stats['column', 'mean', 0] -- get mean statistics for a column at seq_from=0
            stats['column', 'mean', 0, 1] -- get mean statistics for a column at seq_from=0, seq_to=1

        Returns:
            The .df dataframe filtered by the given spec
        """
        df = self.df
        column, statistic, *seq = spec if isinstance(spec, (list, tuple)) else (spec, None)
        column = None if column == '*' else column
        seq_from, seq_to = self._expand_seq(seq, default='baseline', column=column, statistic=statistic) if seq else (
            None, None)
        flt = df['column'].isin(ensure_list(column)) if column else (df.index == df.index)
        flt &= df['statistic'].isin(ensure_list(statistic)) if statistic else True
        flt &= df['seq_from'].isin(ensure_list(seq_from)) if seq_from is not None else True
        flt &= df['seq_to'].isin(ensure_list(seq_to)) if seq_to is not None else True
        return df[flt]

    def plot(self, column=None, statistic=None, seq=None, kind='dist', ax=None, sample=None, logx=False,
             logy=False, xlim=None, ylim=None, **kwargs):
        """ plot drift statistics

        Plots drift statistics for a given column, statistic, seq_from, seq_to. If no column is given,
        plots all columns for the given seq_from, seq_to. If no seq_from, seq_to is given, plots the
        statistics for the entire sequence.

        Can plot either a distribution or a timeline plot, depending on the kind= parameter.
        For distributions, the baseline and target histograms are plotted. For timelines, the metric is
        plotted over the sequence. For numeric columns, the histogram is plotted. For categorical
        columns, the group counts are plotted.

        Distribution plots use the sample statistics taken at snapshot time. If sample=N is given,
        the histogram is re-sampled to N samples for numeric columns.

        Args:
            column (str|list): the column to plot, or a list of columns
            statistic (str): the statistic to plot, defaults to 'mean'
            seq (int|tuple): the sequence to plot, or a tuple of (seq_from, seq_to)
            kind (str): the kind of plot, one of 'dist', 'time'
            ax (matplotlib.Axes): the axes to plot on
            sample (int): the number of samples to draw from the histogram
            logx (bool): whether to use a log scale on the x-axis
            logy (bool): whether to use a log scale on the y-axis
            xlim (tuple): the x-axis limits
            ylim (tuple): the y-axis limits
            **kwargs: additional keyword arguments to pass to the plot function

        Returns:
            matplotlib.Axes: the axes the plot was drawn on
        """
        statistic = statistic or 'mean'
        seq = seq or self.seq(column=column, statistic=statistic)
        if isinstance(column, str):
            ax = self._plot_column(column, statistic, seq, kind, ax, sample=sample, **kwargs)
        else:
            columns = list(column) if isinstance(column, (list, tuple)) else None
            ax = self._plot_all(statistic, seq, kind, ax, columns=columns, **kwargs)
        if logx:
            plt.xscale('log')
        if logy:
            plt.yscale('log')
        if xlim:
            plt.xlim(*xlim)
        if ylim:
            plt.ylim(*ylim)
        return ax

    def _plot_column(self, column, statistic, seq, kind, ax, sample=None, **kwargs):
        s1, s2 = seq if isinstance(seq, (list, tuple)) else [seq, seq]
        baseline_df = self[column, statistic, (s1, None)]
        target_df = self[column, statistic, (None, s2)]
        baseline = baseline_df['baseline'].iloc[0]
        target = target_df['target'].iloc[0]
        dt1 = baseline_df['dt_from'].iloc[0]
        dt2 = target_df['dt_to'].iloc[0]
        if kind == 'dist':
            ax = self._plot_dist(column, statistic, s1, s2, baseline, target, dt1, dt2, ax, sample=sample, **kwargs)
        elif kind == 'time':
            ax = self._plot_timeline(column, statistic, s1, s2, baseline, target, dt1, dt2, ax, **kwargs)
        return ax

    def _plot_all(self, statistic, seq, kind, ax, columns=None, **kwargs):
        df = self.as_dataframe(statistic=statistic)
        df = df[df['column'].isin(columns)] if columns else df
        # -- convert to column oriented data to plot all features for each seq
        dfx = pd.pivot_table(df, index='column', columns='seq_to', values='metric')
        ax = dfx.plot.bar()
        plt.title('Drift statistics for all features')
        # -- move legend outside of plot
        plt.legend(loc='upper left', bbox_to_anchor=(1, 1))
        return ax

    def _plot_dist(self, column, statistic, s1, s2, baseline, target, dt1, dt2, ax, sample=None, **kwargs):
        # prepare drift message
        drift_ind = 'detected' if self[column, statistic]['drift'].sum() > 0 else 'not detected'
        drift_stats = self[column, statistic, (None, s2)].iloc[0]['stats']
        drift_score = self[column, statistic, (None, s2)].iloc[0]['score']
        drift_msg = ", ".join((f'S={drift_score:.3f}', f'{drift_stats}'))
        drift_text = f'{drift_ind} ({drift_msg})'
        # plot feature distribution
        for period in (baseline, target):
            if 'hist' in period:
                counts, edges = period['hist']
                if sample:
                    # perform re-sampling of data if requested
                    stats_calc = DriftStatsCalc()
                    h = stats_calc.sample_from_hist(counts, edges, n=sample)
                    counts, edges = np.histogram(h, bins=len(edges))
                ax = plt.stairs(counts, edges, fill=True, alpha=.8, **kwargs)
            if 'groups' in period:
                ax = plt.bar(period['groups'].keys(), period['groups'].values(), alpha=.8, **kwargs)
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
               .pivot_table(index='seq_to',
                            columns='column',
                            values='metric')
               )
        ax = dfx.plot.line(style='-', marker='X')
        if ax:
            drift_text = 'detected' if dff['drift'].sum() > 0 else 'not detected'
            plt.suptitle(f'{column} distribution')
            plt.title(f'Drift {drift_text}\nBaseline: {dt1} Target: {dt2}', fontsize=8)
            # plt.xlabel('seq_from')
        return ax

    def _expand_seq(self, seq, default=None, column=None, statistic=None):
        if isinstance(seq, (list, tuple)):
            if len(seq) and isinstance(seq[0], (list, tuple)):
                seq_from, seq_to = seq[0]
            elif len(seq) and default == 'baseline':
                seq_from, seq_to = seq[0], None
            elif len(seq):
                seq_from, seq_to = None, seq[0]
            else:
                seq_from, seq_to = None, None
        elif default == 'baseline':
            seq_from, seq_to = seq, None
        elif default == 'target':
            seq_from, seq_to = None, seq
        else:
            seq_from, seq_to = None, seq
        seq_min, seq_max = self.seq(column=column, statistic=statistic)
        seq_from = seq_from if seq_from is None or seq_from >= 0 else (seq_max + seq_from)
        seq_to = seq_to if seq_to is None or seq_to >= 0 else (seq_max + seq_to + 1)
        seq_to = seq_to if int(seq_to or 0) > int(seq_from or 0) else None
        return seq_from, seq_to

    def baseline(self, column, seq=None):
        """ get the baseline statistics

        Args:
            column (str): the column to get statistics for
            seq (int): the sequence to get statistics for

        Returns:
            DriftStatsSeries: the statistics for the target period, this is a pd.Series with
              convenience methods for plotting and describing the statistics, using .hist() and
              .describe() respectively
        """
        return self._stats_series('baseline', column, seq)

    def target(self, column, seq=None):
        """ get the target statistics

        Args:
            column (str): the column to get statistics for
            seq (int): the sequence to get statistics for

        Returns:
            DriftStatsSeries: the statistics for the target period, this is a pd.Series with
              convenience methods for plotting and describing the statistics, using .hist() and
              .describe() respectively
        """
        return self._stats_series('target', column, seq)

    def _stats_series(self, period, column, seq):
        # return a StatsSeries for a given period, column, statistic, seq
        col_df = self[column, None, seq].iloc[0]
        col_s = DriftStatsSeries(col_df[period], name=col_df['column'])
        return col_s

    def as_dataframe(self, drift_data=None, **query):
        drift = drift_data or self.drifts

        if isinstance(drift, list):
            return self._filter_df(pd.concat([self.as_dataframe(d) for d in drift]
                                             or [pd.DataFrame()]), **query)

        info = drift['info']
        stats = drift['stats']

        matcher = info.get('columns_map', {})
        _c = lambda d, c, s: matcher.get(d, matcher).get(c, c) if c not in s['stats'] else c

        def drift_records(stats):
            for column in stats:
                for stat, values in stats[column].items():
                    d1 = info['baseline']
                    d2 = info['target']
                    yield {
                        'column': column,
                        'statistic': stat,
                        'drift': values['drift'],
                        'metric': values['metric'],
                        'score': values.get('score'),
                        'pvalue': values.get('pvalue'),
                        'stats': ','.join(values.get('stats', [stat])),
                        'kind': info['baseline']['info']['kind'],
                        'dt_from': pd.to_datetime(info['dt_from']),
                        'dt_to': pd.to_datetime(info['dt_to']),
                        'seq_from': info['seq'][0],
                        'seq_to': info['seq'][1],
                        'baseline': d1['stats'][_c('d1', column, d1)],
                        'target': d2['stats'][_c('d2', column, d2)],
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


class DriftStatsSeries(pd.Series):
    def __init__(self, values, **kwargs):
        super().__init__(values, **kwargs)

    def hist(self, *args, sample=False, **kwargs):
        return self.plot(sample=sample, **kwargs)

    def plot(self, sample=False, **kwargs):
        if 'hist' in self:
            counts, edges = self['hist']
            if sample:
                # perform re-sampling of data if requested
                stats_calc = DriftStatsCalc()
                h = stats_calc.sample_from_hist(counts, edges, n=sample)
                counts, edges = np.histogram(h, bins=len(edges))
            ax = plt.stairs(counts, edges, fill=True, alpha=.8, **kwargs)
        elif 'groups' in self:
            ax = plt.bar(self['groups'].keys(), self['groups'].values(), alpha=.8, **kwargs)
        else:
            raise ValueError('no histogram or groups found in drift data')
        return ax

    def describe(self, **kwargs):
        if 'hist' in self:
            percentiles = pd.Series(self['percentiles'][0], index=self['percentiles'][1])
            info = pd.concat([self, percentiles], axis=0)
            info = info.drop(['hist', 'percentiles'])
        else:
            info = self
        return info
