import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from scipy.stats import ks_2samp, chisquare, wasserstein_distance


class DriftStatsCalc:
    def ks_2samp(self, d1, d2, ci=.95):
        # two-sample Kolmogorov-Smirnov test for goodness of fit
        # -- H0: d1, d2 are from the same distribution (=> no drift)
        # -- H1: alternative (=> drift)
        # -- H0 is rejected if pvalue < 1 - ci (default: 0.05)
        # https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ks_2samp.html
        result = ks_2samp(d1, d2)
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

    def describe(self, column=None, statistic=None, percentiles=None, **query):
        df = self.as_dataframe(self.drifts, column=column, statistic=statistic, **query)
        return df.groupby(['column', 'statistic'])[['metric', 'pvalue']].describe(percentiles=percentiles).fillna(
            0).round(2)

    def drifted(self, column=None, statistic=None, summary=False, details=False, **query):
        df = self.as_dataframe(self.drifts, column=column, statistic=statistic, **query)
        flt = df['drift'] == True
        drifted_seqs = (df[flt][['seq_from', 'seq_to']]
                        .drop_duplicates()
                        .apply(lambda v: (v['seq_from'], v['seq_to']), axis=1)
                        .tolist())
        result = False if not summary else {}
        if summary:
            key = ['column'] if column else ['kind']
            result = (df.groupby(key)['drift'].sum() > 0).to_dict()
            result['seqs'] = drifted_seqs
        elif not df.empty:
            result = df[flt] if details else df[flt]['drift'].sum() > 0
        return result

    def __getitem__(self, column):
        df = self.df
        column, statistic, *seq = column if isinstance(column, (list, tuple)) else (column, None)
        seq_from, seq_to = self._expand_seq(seq, default='baseline', column=column, statistic=statistic) if seq else (
        None, None)
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
        drift_score = self[column, statistic, (None, s2)].iloc[0]['score']
        drift_msg = ", ".join((f'S={drift_score:.3f}', f'{drift_stats}'))
        drift_text = f'{drift_ind} ({drift_msg})'
        # plot feature distribution
        for period in (baseline, target):
            if 'hist' in period:
                counts, edges = period['hist']
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
            return self._filter_df(pd.concat([self.as_dataframe(d) for d in drift]
                                             or [pd.DataFrame()]), **query)

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
                        'score': values.get('score'),
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
