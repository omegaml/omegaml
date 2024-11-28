import math

import pandas as pd


class ExperimentStatistics:
    class options:
        time_events = ['start', 'stop']
        tp_unit = 60
        groupby = 'run'
        time_key = 'latency'
        percentiles = [.25, .5, .75]  # same default as pandas.DataFrame.describe()
        batchsize = 10000

    def __init__(self, tracker):
        self.tracker = tracker

    def __repr__(self):
        return f"{self.__class__.__name__}({self.tracker})"

    def data(self, **kwargs):
        return self.tracker.data(**kwargs)

    def align_index(self, df, key=None):
        """ align the index of statistics DataFrames to event/key """
        df['event'] = 'metric'
        df['key'] = key
        idx_cols = ['event', 'key']
        df.set_index(idx_cols, inplace=True)

    def summary(self, time_key=None, time_events=None, percentiles=None,
                groupby=None, tp_unit=None, perf_stats=False, **kwargs):
        """ build a summary of the experiment

        Args:
            time_key (str): the key to use for duration, defaults to 'latency'
            time_events (list): the events to use for duration, defaults to ['start', 'stop']
            percentiles (list): the percentiles to pass to pandas.DataFrame.describe(), used
              to calculate metric and duration statistics, defaults to [.25, .5, .75]
            groupby (str): the column to group by for duration calculation, defaults to 'run'
            perf_stats (bool): if True, calculate performance statistics, defaults to False
            **kwargs: any filter arguments to pass to exp.data(), by default sets run='all'

        Notes:
            * perf_stats=True calculates performance statistics on throughput and utilization.
              Since these values are derived from the latency of algorithm execution (i.e. not
              system metrics) these are not included by default. The statistics provide an accurate
              view as far as the algorithm's execution is concerned, yet may not reflect actual system
              load.

              The statistics are calculated as follows:

              * latency: duration of each event
              * throughput: events / latency
              * throughput_eff: number of events / duration
              * utilization: throughput_eff / throughput

              For each statistic the percentiles are calculated across all events in the run.

        Returns:
            DataFrame with summary statistics for all metrics and duration
        """

        time_events = time_events or self.options.time_events
        tp_unit = tp_unit or self.options.tp_unit  # throughput units in seconds (3600 = 1 hour)
        percentiles = percentiles or self.options.percentiles
        kwargs.setdefault('run', 'all')
        metrics = self.metrics(percentiles=percentiles, groupby='', **kwargs)
        duration = self.latency(time_key=time_key, time_events=time_events, groupby=groupby,
                                percentiles=percentiles, **kwargs)
        if not perf_stats:
            return pd.concat([metrics, duration])
        throughput = self.throughput(tp_unit=tp_unit, time_events=time_events, **kwargs)
        utilization = self.utilization(tp_unit=tp_unit, time_events=time_events, **kwargs)
        return pd.concat([metrics, duration, throughput, utilization], copy=False)

    def metrics(self, event=None, percentiles=None, groupby=None, **kwargs):
        """ calculate percentiles for all metric events

        This queries exp.data(event='metric', **kwargs) and calculates the percentiles for each
        metric, resulting from exp.log_metric() calls. The percentiles are calculated across all
        runs selected.

        Args:
             percentiles (list): the percentiles to pass to pandas.DataFrame.describe()
             groupby (str): the column to group by for duration calculation, defaults to 'run',
                to summarize metrics across all runs set groupby=''
             **kwargs: any filter arguments to pass to exp.data(), by default sets run='all'

        Returns:
            DataFrame with percentiles for each metric

        .. versionchanged:: 0.16.4
            Metrics are calculated by run (new default). To get back the previous behavior,
            calculated across all runs, set groupby=''.
        """
        # metrics - percentiles for each metric
        event = event or 'metric'
        groupby = [groupby or self.options.groupby] if groupby not in (0, '', -1) else []
        groups = dict.fromkeys(groupby + ['event', 'key'])

        def stats(data):
            metrics = (data
                       .groupby(list(groups))
                       .apply(lambda v: (v['value']
                                         .describe(percentiles=percentiles)))
                       )
            return metrics

        batches = self.data(event=event, batchsize=self.options.batchsize, **kwargs)
        aggstats = (v for v in map(stats, batches) if v is not None)
        return pd.concat(aggstats, copy=False)

    def latency(self, time_key=None, time_events=None, percentiles=None,
                groupby=None, **kwargs):
        """ calculate latency for each group of events

        This queries exp.data(event=time_events, **kwargs) and calculates the duration for each
        group of events. time_events defaults to ['start', 'stop'] and time_key defaults to 'latency'.
        This means the duration is calculated as the difference between the first and last event of
        each run. The percentiles are calculated across all runs selected.

        Args:
            time_key (str): the key to use for duration, defaults to 'latency'
            time_events (list): the events to use for duration, defaults to ['start', 'stop']
            percentiles (bool|list): the percentiles to pass to pandas.DataFrame.describe()
            groupby (str): the column to group by for duration calculation, defaults to 'run'
            **kwargs:  any filter arguments to pass to exp.data(), by default sets run='all'

        Returns:
            DataFrame with latency statistics for each group of events. If percentiles is None
            the DataFrame includes one event for each group with the 'latency' key added. If
            percentiles is True

        Notes:
            1. group by run
            2. calculate duration as the difference between start and stop for each group
            3. calculate percentiles across all groups
        """
        groupby = groupby or self.options.groupby
        time_key = time_key or self.options.time_key
        time_events = time_events or self.options.time_events
        percentiles = None if not percentiles else (percentiles or self.options.percentiles)

        def stats(time_data):
            duration = (time_data
                        .groupby(groupby)
                        .apply(lambda v: ((v['dt'].max() - v['dt'].min())
                                          .total_seconds())
                               )
                        )
            if percentiles:
                duration = (duration
                            .describe(percentiles=None if percentiles is True else percentiles)
                            .to_frame()
                            .T)
                self.align_index(duration, time_key)
            else:
                duration = (self.data(**kwargs)
                            .groupby(groupby)
                            .first()
                            .reset_index()
                            .merge((duration
                                    .reset_index(name='latency')),
                                   on=groupby)
                            )
            return duration

        batches = self.data(event=time_events, batchsize=self.options.batchsize, **kwargs)
        aggstats = (v for v in map(stats, batches) if v is not None)
        return pd.concat(aggstats, copy=False)

    def throughput(self, time_key=None, tp_unit=None, groupby=None, time_events=None, percentiles=None, **kwargs):
        """ calculate throughput for each group of events

        This queries exp.data(event=time_events, **kwargs) and calculates throughput for each
        group of events. time_events defaults to ['start', 'stop'] and time_key defaults to 'latency'.
        Throughput is calculated as the number of events per time unit (tp_unit).

        Args:
            time_key (str): the key to use for duration, defaults to 'latency'
            tp_unit (int): the throughput unit to use, defaults to 60
            groupby (str): the column to group by for duration calculation, defaults to 'run'
            time_events (list): the events to use for duration, defaults to ['start', 'stop']
            percentiles (list): the percentiles to pass to pandas.DataFrame.describe()
            **kwargs:  any filter arguments to pass to exp.data(), by default sets run='all'

        Returns:
            DataFrame with throughput statistics for each group of events

        Notes:
            1. calculate throughput as the number of events / duration
        """
        time_events = time_events or self.options.time_events
        time_key = time_key or self.options.time_key
        groupby = groupby or self.options.groupby
        tp_unit = tp_unit or self.options.tp_unit

        def stats(time_data):
            throughput = (time_data
                          .groupby(groupby)
                          .apply(lambda v: (tp_unit / max((v['dt'].max() - v['dt'].min())
                                                          .total_seconds(), 1))
                                 )
                          .describe(percentiles=percentiles)
                          .to_frame()
                          .T
                          )
            self.align_index(throughput, f'group_{time_key}')
            return throughput

        batches = self.data(event=time_events, batchsize=self.options.batchsize, **kwargs)
        aggstats = (v for v in map(stats, batches) if v is not None)
        return pd.concat(list(aggstats))

    def group_latency(self, time_events=None, percentiles=None, time_slots=None, **kwargs):
        """ calculate latency for each group of events

        This queries exp.data(event=time_events, **kwargs) and calculates the duration for equal-
        length groups of events), specified by the number of time_slots (default 10% of the total
        event count). time_events defaults to ['start', 'stop'] and time_key defaults to 'latency'.
        The percentiles are calculated across all groups. Note the group latency uses walk-clock
        time, i.e. the time between the first and last event in each group. This is different from
        the actual latency, which is the time between the first start and last stop event of each run.

        Args:
            time_events (list): the events to use for duration, defaults to ['start', 'stop']
            percentiles (list): the percentiles to pass to pandas.DataFrame.describe()
            time_slots (int): the number of time slots to use for grouping, defaults to
               10% of the total number of events
            **kwargs:  any filter arguments to pass to exp.data(), by default sets run='all'

        Returns:
            DataFrame with latency statistics for each group of events

        Notes:
            1. cut the events into bins of 10% of the total number of events
            2. group by bins
            3. calculate total latency as the percentiles across all bins
        """
        time_events = time_events or self.options.time_events
        time_data = self.data(event=time_events, **kwargs)
        time_slots = time_slots or math.ceil(len(time_data) * .1)
        bins = pd.cut(time_data['dt'], bins=time_slots)
        latency = (time_data
                   .groupby(bins)
                   .apply(lambda v: (max((v['dt'].max() - v['dt'].min())
                                         .total_seconds(), 1))
                          )
                   .describe(percentiles=percentiles)
                   .to_frame()
                   .T)
        self.align_index(latency, 'latency')
        return latency

    def utilization(self, tp_unit=None, time_events=None, percentiles=None, **kwargs):
        """ calculate utilization for each group of events

        Calculate utilization as the effective throughput (throughput_eff) divided by the
        actual throughput. The effective throughput is the number of events per time unit,
        thus the utilization is the number of events per time unit divided by the theoretical
        maximum of events per time unit.

        Args:
            tp_unit (int): the throughput unit to use, defaults to 60
            time_events (list): the events to use for duration, defaults to ['start', 'stop']
            percentiles (list): the percentiles to pass to pandas.DataFrame.describe()
            **kwargs:  any filter arguments to pass to exp.data(), by default sets run='all'

        Returns:
            DataFrame with utilization statistics for each group of events

        Notes:
            1. same calculation as latency
            2. calculate throughput for each bin (number of events / duration)
               -- note we divide by 2 since we have start and stop events
            3. calculate percentiles across all bins
            4. calculate utilization as throughput / throughput_eff
        """

        tp_unit = tp_unit or self.options.tp_unit
        time_events = time_events or self.options.time_events
        time_data = self.data(event=time_events, **kwargs)
        time_slots = math.ceil(len(time_data) * .1)
        bins = pd.cut(time_data['dt'], bins=time_slots)
        throughput = self.throughput(tp_unit=tp_unit, time_events=time_events, **kwargs)
        throughput_eff = (time_data
                          .groupby(bins)
                          .apply(lambda v: ((len(v) // 2) / max((v['dt'].max() - v['dt'].min())
                                                                .total_seconds() * tp_unit, 1))
                                 )
                          .describe(percentiles=percentiles)
                          .to_frame()
                          .T)
        self.align_index(throughput_eff, 'troughput_eff')
        utilization = (throughput_eff.reset_index(drop=True) /
                       throughput.reset_index(drop=True))
        self.align_index(utilization, 'utilization')
        return utilization
