import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from omegaml.util import ensure_list, extend_instance
from scipy.stats import ks_2samp, wasserstein_distance, entropy, chisquare, chi2


class DriftStatsCalc:
    """ Drift statistics calculator

    The DriftStatsCalc class calculates drift statistics for two distributions.
    The distributions can be either numeric or categorical. The calculator is
    extensible by mixins, which can be added to the DriftStatsCalc instance.

    The DriftStatsCalc class provides the following metrics:
    * ks: two-sample Kolmogorov-Smirnov test for goodness of fit
    * wasserstein: Wasserstein distance between two distributions
    * chisquare: one-way chi-square test

    The available metrics and their associated function can be queried
    by calling DriftStatsCalc.metrics(). The metrics are grouped by kind,
    either 'numeric' or 'categorical'. The metrics can be called by name
    using DriftStatsCalc.metrics(kind)[metric_name], e.g. DriftStatsCalc.metrics('numeric')['ks'].

    Args:
        seed (int): the seed to use for reproducibility of drift statistics. This
          sets the seed for the random number generator used for sampling histograms (default: 42),
          using np.random.default_rng(seed=seed).

    Usage:
        # calculate drift statistics for two distributions
        stats_calc = DriftStatsCalc()
        stats_calc.metrics() -- get all metrics
        stats_calc.metrics('numeric') -- get all numeric metrics
        stats_calc.metrics('categorical') -- get all categorical metrics
        ks = stats_calc.metrics('numeric')['ks']
        result = ks(d1, d2) -- calculate the Kolmogorov-Smirnov statistic for d1, d2

        # the result of any drift metric method is a dict with the following keys
        result = {
            'metric': 0.1, # the metric value
            'score': 0.5, # the score of the metric (0.5 means no drift, 0 - 0.5 negative drift,
                0.5 - 1 positive drift)
            'drift': True, # a boolean indicating drift
            'pvalue': 0.05, # the pvalue of the test
            'location': 3, # location of the statistic
        }

        # add a mixin to the DriftStatsCalc instance
        class MyCalcMixin:
            def _initmixin(self):
                # this method is called by the DriftStatsCalc constructor
                self._metrics['numeric']['my_metric'] = self.my_metric

            def my_metric(self, d1, d2):
                return {
                    'metric': ..., # the metric value
                    'score': ..., # the score of the metric
                    'drift': ..., # a boolean indicating drift
                    'pvalue': ..., # the pvalue of the test
                    'location': ..., # the location of the statistic
                }

        with om.runtime.experiment('test') as exp:
            mon = DataDriftMonitor('foo', store=om.datasets, tracking=exp)
            mon.statscalc._apply_mixins([MyCalcMixin])

        Alternatively, the DriftStatsCalc instance can be extended with mixins
        specified in defaults.OMEGA_MONITOR_MIXINS['DriftStatsCalc'].
    """

    def __init__(self, seed=42):
        # we use a fixed seed for reproducibility of drift statistics
        # -- self.rng is used to sample histograms
        # -- sampling causes drift statistics to be different each time
        # -- using a fixed seed allows for reproducibility
        self.rng = np.random.default_rng(seed=seed)
        # metrics used to calculate the mean drift score
        self.mean_metrics = ['ks', 'wasserstein', 'chisq']
        # drift metrics
        self._metrics = {
            'numeric': {
                'ks': self.ks_2samp,
                'wasserstein': self.wasserstein_distance,
                'kld': self.kl_divergence,
                'jsd': self.js_divergence,
            },
            'categorical': {
                'chisquare': self.chisquared_test,
                'psi': self.psi,
            },
        }
        self._apply_mixins()

    def _apply_mixins(self, mixins=None):
        """
        apply mixins in defaults.OMEGA_MONITOR_MIXINS
        """
        import omegaml as om
        mixins = mixins or om.defaults.OMEGA_MONITORING_MIXINS.get('DriftStatsCalc', [])
        for mixin in mixins:
            extend_instance(self, mixin)

    def metrics(self, kind=None):
        return self._metrics.get(kind) if kind else self._metrics

    def ks_2samp(self, d1, d2, ci=.95, **kwargs):
        # two-sample Kolmogorov-Smirnov test for goodness of fit
        # -- H0: d1, d2 are from the same distribution (=> no drift)
        # -- H1: alternative (=> drift)
        # -- H0 is rejected if pvalue < 1 - ci (default: 0.05)
        # https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ks_2samp.html
        result = ks_2samp(d1, d2, method='asymp')
        score = abs(result.statistic)
        is_drift = result.pvalue < (1 - ci)
        return {
            'metric': result.statistic,
            'score': score,
            'drift': is_drift,
            'pvalue': result.pvalue,
            'location': result.statistic_location,
        }

    def psi(self, baseline, target, ci=.99, sd=None, **kwargs):
        """Calculate Population Stability Index (PSI)"""

        def calculate_psi(expected, actual, bins=10):
            hist_expected, _ = np.histogram(expected, bins=bins, density=True)
            hist_actual, _ = np.histogram(actual, bins=bins, density=True)

            hist_expected += 1e-10  # Avoid division by zero
            hist_actual += 1e-10

            psi_value = np.sum(
                (hist_expected - hist_actual) * np.log(hist_expected / hist_actual)
            )
            return psi_value

        psi_value = calculate_psi(baseline, target)
        drift_detected = psi_value > 0.25  # typical threadhold
        score = min(1, psi_value / 0.5)  # normalizing score to 0-1
        return {
            "drift": drift_detected,
            "metric": psi_value,
            "score": score,
            "pvalue": None,
            "location": None,
        }

    def kl_divergence(self, baseline, target, ci=.99, sd=None, **kwargs):
        """Calculate Kullback-Leibler Divergence (KL)"""
        hist_baseline, _ = np.histogram(baseline, bins=100, density=True)
        hist_target, _ = np.histogram(target, bins=100, density=True)

        hist_baseline += 1e-10  # Avoid division by zero
        hist_target += 1e-10

        kl_value = entropy(hist_baseline, hist_target)
        drift_detected = kl_value > 0.1  # Threshold for drift
        score = min(1.0, kl_value / 1.0)  # Normalize score to 0-1

        return {
            "drift": drift_detected,
            "metric": kl_value,
            "score": score,
            "pvalue": None,
            "location": None,
        }

    def js_divergence(self, baseline, target, ci=.99, sd=None, **kwargs):
        """Calculate Jensen-Shannon Divergence (JS)"""
        hist_baseline, _ = np.histogram(baseline, bins=100, density=True)
        hist_target, _ = np.histogram(target, bins=100, density=True)
        hist_baseline += 1e-10  # Avoid division by zero
        hist_target += 1e-10
        m = 0.5 * (hist_baseline + hist_target)
        js_value = 0.5 * (entropy(hist_baseline, m) + entropy(hist_target, m))
        drift_detected = js_value > 0.05  # Threshold for drift
        score = min(1.0, js_value / 0.2)  # Normalize score to 0-1
        return {
            "drift": drift_detected,
            "metric": js_value,
            "score": score,
            "pvalue": None,
            "location": None,
        }

    def wasserstein_distance(self, d1, d2, ci=.95, sd=None, **kwargs):
        # Wasserstein distance between two distributions
        # calculates a normalized distance between two distributions
        # -- normalized by the standard deviation of d1
        # -- H0: d1, d2 are from the same distribution (=> no drift)
        # -- H1: alternative (=> drift)
        # -- H0 is rejected if normalized distance is > (1 - ci) sd
        # https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wasserstein_distance.html
        sd = sd or np.std(d1, ddof=1)
        wd = wasserstein_distance(d1, d2)
        score = min(wd / sd, 1)
        is_drift = (score > (1 - ci))
        return {
            'metric': wd,
            'score': score,
            'drift': is_drift,
            'pvalue': None,
            'location': None,
        }

    def chisquared_test(self, d1, d2, ci=.99, sd=None, **kwargs):
        # one-way chi-square test
        # -- H0: categorical frequencies in d2 match the expectation in d1 (=> no drift)
        # -- H1: alterantive (=> drift)
        # -- H0 is rejected if pvalue < (1 - ci)
        # https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chisquare.html#scipy.stats.chisquare
        result = chisquare(f_obs=d2, f_exp=d1)
        is_drift = result.pvalue < (1 - ci)
        # min-max normalize score to 0-1
        # -- min is 0, .999 percentile is chi2.ppf(0.999, ddof)
        score = min(result.statistic / chi2.ppf(0.999, len(d2) - 1), 1)
        return {
            'metric': result.statistic,
            'score': score,
            'drift': is_drift,
            'pvalue': result.pvalue,
            'location': None,
        }

    def sample_from_hist(self, hist, edges, n=100):
        n = 100 if n is True else n
        probs = hist / np.sum(hist)
        return self.rng.choice(np.linspace(edges[0], edges[-1], len(edges) - 1), n, p=probs)

    def sample_from_groups(self, counts, groups, n=100):
        probs = np.array(counts) / np.sum(counts)
        return self.rng.choice(groups, size=n, p=probs)

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


class DriftStats:
    """ Drift statistics for a given column, statistic or sequence

    Drift statistics are represented for a given column, statistic or sequence, or a combination
    of these.

    Usage:
        stats = DriftStats(drifts)
        stats['column'] -- get all statistics for a column
        stats['column', 'mean'] -- get mean statistics for a column
        stats['column', 'mean', 0] -- get mean statistics for a column at seq_from=0
        stats['column', 'mean', 0, 1] -- get mean statistics for a column at seq_from=0, seq_to=1

    Args:
        data (list[dict]): the drift statistics data, a list of dicts, with the following keys:
            * info: the drift info, a dict with the following
                - dt_from: the datetime of the baseline period
                - dt_to: the datetime of the target period
                - ci: the confidence interval of the test
                - seq: the sequence of the drift
                - baseline: the baseline snapshot
                - target: the target snapshot
            * stats: the drift statistics, a dict with the following
                - column: the column name
                - statistic: the statistic name
                - drift: a boolean indicating drift
                - metric: the drift metric
                - score: the drift score
                - pvalue: the pvalue of the test
                - stats: the statistics used for the test
            * kind: the kind of drift, one of 'data', 'feature', 'label'
        monitor (ModelMonitor): the monitor that generated the drift statistics

    """

    def __init__(self, data, monitor=None):
        self.drifts = data
        self.monitor = monitor
        self._df = None

    def __repr__(self):
        return f'DriftStats({self.monitor},drifts={len(self.drifts)})'

    @property
    def df(self):
        if self._df is None:
            self._df = self.as_dataframe(self.drifts).reset_index()
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
            statistic (str): the statistic to filter by, defaults to 'mean'
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
        statistic = statistic or 'mean'
        df = self.as_dataframe(self.drifts, column=column, statistic=statistic, **query)
        if df.empty:
            result = {
                'columns': {},
                'summary': {},
                'info': {'seq': []},
            }
        else:
            # prepare summary
            drifted = df['drift']
            dfx = df[drifted]
            drifted_seqs = (dfx[['seq_from', 'seq_to']]
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
                'score': (df.groupby('kind')
                          .apply(lambda v: v['score'].max())
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
            df['score'] = pd.Series([s['score'].get(k) for k in df['kind']])
            result = df
        return result

    def __getitem__(self, spec):
        """
        Get drift statistics for a given column, statistic, seq_from, seq_to. This
        is the equivalent of .select(column, statistic, seq_from, seq_to), however
        allows for a more concise syntax.

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
        column, statistic, *seq = spec if isinstance(spec, (list, tuple)) else (spec, None)
        column = None if column == '*' else column
        return self.select(column=column, statistic=statistic, seq=seq)

    def select(self, column=None, statistic=None, seq=None):
        """
        Get drift statistics for a given column, statistic, seq_from, seq_to

        Args:
            column (str): the column to filter by
            statistic (str): the statistic to filter by
            seq (int|tuple): the sequence to filter by, or a tuple of (seq_from, seq_to)

        Usage:
            stats['column'] -- get all statistics for a column
            stats['column', 'mean'] -- get mean statistics for a column
            stats['column', 'mean', 0] -- get mean statistics for a column at seq_from=0
            stats['column', 'mean', 0, 1] -- get mean statistics for a column at seq_from=0, seq_to=1

        Returns:
            The .df dataframe filtered by the given spec
        """
        df = abortIfEmpty(self.df, "no data available")
        seq_from, seq_to = self._expand_seq(seq, default='baseline', column=column, statistic=statistic) if seq else (
            None, None)
        flt = df['column'].isin(ensure_list(column)) if column else (df.index == df.index)
        flt &= df['statistic'].isin(ensure_list(statistic)) if statistic else True
        flt &= df['seq_from'].isin(ensure_list(seq_from)) if seq_from is not None else True
        flt &= df['seq_to'].isin(ensure_list(seq_to)) if seq_to is not None else True
        return df[flt]

    def plot(self, column=None, statistic=None, seq=None, kind='dist', ax=None, sample=True, logx=False,
             logy=False, xlim=None, ylim=None, raw=False, **kwargs):
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
            raw (bool): if True, return the tuple (ax, data, type) else ax
            **kwargs: additional keyword arguments to pass to the plot function

        Returns:
            matplotlib.Axes: the axes the plot was drawn on (raw=False)
            (matplotlib.Axes, data, type): the plot axes, the data, and the kind of plot (raw=True)
        """
        statistic = statistic or 'mean'
        statistic = None if statistic in ('*', 'all', 'any') else statistic
        valid_plots = ('dist', 'hist', 'time', 'box')
        seq = self._expand_seq(seq, column=column, statistic=statistic)
        assert kind in valid_plots, f'kind must be one of {valid_plots}, got {kind}'
        if isinstance(column, str):
            ax = self._plot_column(column, statistic, seq, kind, ax, sample=sample, raw=raw, **kwargs)
        else:
            columns = list(column) if isinstance(column, (list, tuple)) else None
            ax = self._plot_all(statistic, seq, kind, ax, columns=columns, raw=raw, **kwargs)
        if logx:
            plt.xscale('log')
        if logy:
            plt.yscale('log')
        if xlim:
            plt.xlim(*xlim)
        if ylim:
            plt.ylim(*ylim)
        return ax

    def _plot_column(self, column, statistic, seq, kind, ax, sample=None, raw=False, **kwargs):
        s1, s2 = seq if isinstance(seq, (list, tuple)) else [seq, seq]
        baseline_df = self[column, statistic, (s1, None)]
        target_df = self[column, statistic, (None, s2)]
        baseline = baseline_df['baseline'].iloc[0]
        target = target_df['target'].iloc[0]
        dt1 = baseline_df['dt_from'].iloc[0]
        dt2 = target_df['dt_to'].iloc[0]
        if kind in ('dist', 'box', 'hist'):
            kind = 'hist' if kind == 'dist' else kind
            ax = self._plot_dist(column, statistic, s1, s2, baseline, target, dt1, dt2, ax, sample=sample,
                                 raw=raw, kind=kind, **kwargs)
        elif kind == 'time':
            ax = self._plot_timeline(column, statistic, s1, s2, baseline, target, dt1, dt2, ax,
                                     raw=raw, **kwargs)
        return ax

    def _plot_all(self, statistic, seq, kind, ax, columns=None, raw=False, **kwargs):
        df = self.as_dataframe(statistic=statistic)
        dt1 = df['dt_from'].iloc[0]
        dt2 = df['dt_to'].iloc[-1]
        df = df[df['column'].isin(columns)] if columns else df
        # -- convert to column oriented data to plot all features for each seq
        if kind == 'time':
            dfx = pd.pivot_table(df, index='seq_to', columns='column', values='metric')
            dfx.index = dfx.index.astype(str)
            ax = dfx.plot.line()
            plottype = 'line'
        else:
            dfx = pd.pivot_table(df, index='column', columns='seq_to', values='metric')
            ax = dfx.plot.bar()
            plottype = 'bar'
        features = columns or 'all'
        plt.suptitle(f'Drift statistics ({features}, {statistic})')
        plt.title(f'Baseline: {dt1} Target: {dt2}', fontsize=8)
        # -- move legend outside of plot
        plt.legend()
        plt.ylim((0, dfx.select_dtypes(include='number').max().max()))
        return (ax, dfx, plottype) if raw else ax

    def _plot_dist(self, column, statistic, s1, s2, baseline, target, dt1, dt2, ax, sample=None,
                   raw=False, kind=None, normalize=False, **kwargs):
        # prepare drift message
        drift_ind = 'detected' if self[column, statistic]['drift'].sum() > 0 else 'not detected'
        drift_stats = self[column, statistic, (None, s2)].iloc[0]['stats']
        drift_score = self[column, statistic, (None, s2)].iloc[0]['score']
        drift_msg = ", ".join((f'S={drift_score:.3f}', f'{drift_stats}'))
        drift_text = f'{drift_ind} ({drift_msg})'
        # plot feature distribution
        kind = kind or 'hist'
        plot_styles = {
            'hist': {
                'baseline': {'alpha': 1.0, 'linestyle': '--', 'fill': False},
                'target': {'alpha': 0.3, 'fill': True},
            },
            'box': {
                'baseline': {'alpha': 1.0},
                'target': {'alpha': 0.3},
            },
        }
        data_style_map = [
            (baseline, 'baseline'),
            (target, 'target')
        ]
        stats_calc = DriftStatsCalc()
        data = None
        ax = None
        plottype = None
        for i, (period, style_id) in enumerate(data_style_map):
            style = plot_styles[kind][style_id]
            style.update(kwargs.get('style', {}).get('baseline', {}))
            if 'hist' in period:
                counts, edges = period['hist']
                if sample or kind == 'box':
                    # perform re-sampling of data if requested
                    N = int(100 if sample is True else sample)
                    values = stats_calc.sample_from_hist(counts, edges, n=N)
                    counts, edges = np.histogram(values, bins=len(edges))
                if kind == 'hist':
                    ax = plt.stairs(counts, edges, **style)
                    data = counts, edges
                    plottype = 'stairs'
                elif kind == 'box':
                    ax = plt.boxplot(values, positions=[i], patch_artist=True, boxprops=style)
                    plt.xticks([0, 1], ['baseline', 'target'])  # Set x-tick labels
                    plottype = 'box'
                    data = values
            if 'groups' in period:
                counts, groups = list(period['groups'].values()), list(period['groups'].keys())
                if sample:
                    values = stats_calc.sample_from_groups(counts, groups)
                    s = pd.Series(values).value_counts(normalize=normalize)
                    counts, groups = s.values, s.index
                if kind == 'hist':
                    ax = plt.bar(groups, counts, **style)
                    data = counts, groups
                    plottype = 'bar'
                elif kind == 'box':
                    ax = plt.boxplot(counts, positions=[i], patch_artist=True, boxprops=style)
                    plt.xticks([0, 1], ['baseline', 'target'])  # Set x-tick labels
                    data = values
                    plottype = 'box'
        if ax:
            plt.suptitle(f'{column} distribution')
            plt.title(f'Drift {drift_text}\nBaseline: {dt1} Target: {dt2}', fontsize=8)
            plt.xlabel(column)
            plt.legend(['baseline', 'target'])
        return (ax, data, plottype) if raw else ax

    def _plot_timeline(self, column, statistic, s1, s2, baseline, target, dt1, dt2, ax, raw=False, **kwargs):
        from matplotlib.dates import DateFormatter
        date_form = DateFormatter("%Y-%m-%d")
        print(column, statistic, s1, s2)
        d1 = self[column, statistic, (s1, None)]
        d2 = self[column, statistic, (None, s2)]
        dff = pd.concat([d1, d2])
        # wide format for plotting
        # -- one column for each column, statistic
        dfx = (dff
               .pivot_table(index='seq_to',
                            columns=['column', 'statistic'],
                            values='metric',
                            aggfunc='max',
                            )
               )
        dfx.index = dfx.index.astype(str)
        ax = dfx.plot.line(style='--', marker='X')
        # Rotate and format the x-axis labels
        plottype = 'line'
        if ax:
            drift_ind = 'detected' if dff['drift'].sum() > 0 else 'not detected'
            drift_stats = dff.iloc[0]['stats']
            drift_score = dff.iloc[0]['score']
            drift_msg = ", ".join((f'S={drift_score:.3f}', f'{drift_stats}'))
            drift_text = f'{drift_ind} ({drift_msg})'
            plt.suptitle(f'{column} timeline')
            plt.title(f'Drift {drift_text}\nBaseline: {dt1} Target: {dt2}', fontsize=8)
            # plt.xlabel('seq_from')
        return (ax, dfx, plottype) if raw else ax

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

    def baseline(self, column=None, seq=None):
        """ get the baseline statistics

        Args:
            column (str): the column to get statistics for. If None, returns all a DataFrame with
                all columns
            seq (int): the sequence to get statistics for

        Returns:
            results (DriftStatsDataFrame|DriftStatsSeries): the statistics for the baseline period

            * DriftStatsSeries: the statistics for the baseline period, this is a pd.Series with
              convenience methods for plotting and describing the statistics, using .hist() and
              .describe() respectively. If column is None, returns a DriftStatsDataFrame

            * DriftStatsDataFrame: the statistics for the baseline period, this is a pd.DataFrame with
              convenience methods for plotting and describing the statistics, using .hist() and
              .describe() respectively
        """
        if column is None:
            return DriftStatsDataFrame([self._stats_series('baseline', column, seq)
                                        for column in self.columns])
        return self._stats_series('baseline', column, seq)

    def target(self, column=None, seq=None):
        """ get the target statistics

        Args:
            column (str): the column to get statistics for
            seq (int): the sequence to get statistics for

        Returns:
            results (DriftStatsDataFrame|DriftStatsSeries): the statistics for the target period

            * DriftStatsSeries: the statistics for the target period, this is a pd.Series with
              convenience methods for plotting and describing the statistics, using .hist() and
              .describe() respectively. If column is None, returns a DriftStatsDataFrame

            * DriftStatsDataFrame: the statistics for the target period, this is a pd.DataFrame with
              convenience methods for plotting and describing the statistics, using .hist() and
              .describe() respectively
        """
        if column is None:
            return DriftStatsDataFrame([self._stats_series('target', column, seq)
                                        for column in self.columns])
        return self._stats_series('target', column, seq)

    def _stats_series(self, period, column, seq):
        # return a StatsSeries for a given period, column, statistic, seq
        col_df = self[column, None, seq].iloc[0]
        col_s = DriftStatsSeries(col_df[period], name=col_df['column'])
        return col_s

    def as_dataframe(self, drift_data=None, **query):
        drift = drift_data or self.drifts

        if isinstance(drift, list):
            if not drift:
                return pd.DataFrame()
            return self._filter_df(pd.concat([self.as_dataframe(drift_data=d) for d in drift]
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
                        'baseline': d1['stats'][_c('d1', column, d1)] | {'len': d1['info']['len']},
                        'target': d2['stats'][_c('d2', column, d2)] | {'len': d2['info']['len']},
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
        """ plot a histogram of the drift statistics

        Args:
            sample (int): the number of samples to draw from the histogram
            *args: additional arguments to pass to the plot

        Returns:
            matplotlib.Axes: the axes the plot was drawn on
        """
        return self.plot(sample=sample, **kwargs)

    def plot(self, sample=False, **kwargs):
        """ plot the drift statistics

        Plot the drift statistics as a histogram or bar plot, depending on the data type.
        For numeric data, a histogram is plotted. For categorical data, a bar plot is plotted.

        Args:
            sample (int): the number of samples to draw from the histogram
            **kwargs:

        Returns:
            matplotlib.Axes: the axes the plot was drawn on
        """
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
        """ describe the drift statistics

        Describe the drift statistics for the given column, statistic, seq_from, seq_to
        """
        if 'hist' in self:
            percentiles = pd.Series(self['percentiles'][0], index=self['percentiles'][1])
            info = pd.concat([self, percentiles], axis=0)
            info = info.drop(['hist', 'percentiles', 'corr'])
        elif 'groups' in self:
            counts = pd.Series(self['groups'])
            info = pd.concat([self, counts], axis=0)
            info = info.drop(['groups'])
        else:
            info = self
        return info

    def sample(self, n=100, seed=None, **kwargs):
        """ sample from the drift statistics

        Sample from the drift statistics for the given column, statistic, seq_from, seq_to.
        The sampling is done from the histogram (numerical columns) and groups data (categorical columns)
        to represent the original distribution.

        Args:
            n (int): the number of samples to take, defaults to 100
            seed (int): the random seed to use (e.g. for reproducibility)
            **kwargs: additional keyword arguments to pass to the sample function

        Returns:
            pd.Series: a Series with the sampled values
        """
        calc = DriftStatsCalc(seed=seed)
        if 'hist' in self:
            counts, edges = self['hist']
            values = calc.sample_from_hist(counts, edges, n=n)
        elif 'groups' in self:
            counts, groups = list(self['groups'].values()), list(self['groups'].keys())
            values = calc.sample_from_groups(counts, groups, n=n)
        else:
            raise ValueError('no histogram or groups found in drift data')
        return pd.Series(values)


class DriftStatsDataFrame(pd.DataFrame):
    def __init__(self, driftseries, **kwargs):
        df = pd.concat(driftseries, axis=1)
        super().__init__(df, **kwargs)

    def __getitem__(self, column):
        return DriftStatsSeries(super().__getitem__(column).dropna())

    def describe(self, **kwargs):
        """
        Describe the drift statistics for all columns

        Args:
            **kwargs: additional keyword arguments to pass to the describe function

        Returns:
            pd.DataFrame: a DataFrame with the drift statistics for all columns
        """
        df = pd.concat([self[c].describe(**kwargs) for c in self.columns], axis=1)
        df.columns = list(self.columns)
        return df

    def sample(self, n=100, seed=None, **kwargs):
        """ sample from all columns

        This samples from all columns in the DataFrame. The sample function is called with the
        given arguments for each column in the DataFrame. The resulting samples are concatenated
        into a new DataFrame with the same columns as the original DataFrame. Note that the
        resulting DataFrame may not match the original dataframe multivariate distribution,
        as each column is sampled independently.

        Args:
            n (int): the number of samples to take, defaults to 100
            seed (int): the random seed to use (e.g. for reproducibility)
            **kwargs: additional keyword arguments to pass to the sample function

        Returns:
            pd.DataFrame: a DataFrame with the sampled values for all columns
        """
        df = pd.concat([self[c].sample(n, seed=seed, **kwargs) for c in self.columns], axis=1)
        df.columns = list(self.columns)
        return df

    def corr(self, method='pearson', **kwargs):
        """ return the correlation matrix for all columns

        Returns the correlation matrix for all numerical columns in the DataFrame. The correlation matrix is
        not re-calculated. It represents the respective correlation at the time of the snapshot. If the
        correlation matrix is not available, the respective entry is NaN. Reasons for NaN entries include
        missing data, categorical data, or other reasons that prevent the calculation of the correlation, such
        as a lack of available memory.

        Args:
            method (str): the correlation method, one of 'pearson' or 'spearman'

        Returns:
            pd.DataFrame: a DataFrame with the correlation matrix for all numerical
              columns
        """
        corr_basedata = self.loc['corr'].dropna()
        corr_data = (r[method] for r in corr_basedata if r[method] is not None)
        corr_df = pd.DataFrame.from_records(corr_data)
        corr_df.index = corr_basedata.index
        return corr_df[sorted(corr_df.columns)].sort_index()

    def plot(self, column, sample=False, **kwargs):
        """ plot histograms for a given column

        this is equivalent to calling DriftStatsDataFrame[column].plot(sample=sample, **kwargs) or
        DriftStatsSeries.plot(sample=sample, **kwargs) for the given column.

        Args:
            column (str): the column to plot
            sample (int): the number of samples to draw from the histogram
            **kwargs: additional keyword arguments to pass to the plot function

        Returns:
            matplotlib.Axes: the axes the plot was drawn on
        """
        return self[column].plot(sample=sample, **kwargs)


def abortIfEmpty(df, error):
    conditions = (
        None,
        isinstance(df, pd.DataFrame) and df.empty
    )
    if any(conditions):
        raise ValueError(error)
    return df
