import pandas as pd

from omegaml.backends.monitoring.base import DriftMonitorBase
from omegaml.backends.monitoring.datadrift import DataDriftMonitor
from omegaml.backends.monitoring.stats import DriftStats
from omegaml.util import tryOr, ensure_list


class ModelDriftMonitor(DriftMonitorBase):
    def __init__(self, resource=None, store=None, query=None, tracking=None, kind=None, **kwargs):
        kind = kind or 'model'
        resource = resource or 'a_model'
        super().__init__(resource=resource, store=store, tracking=tracking, query=query, kind=kind, **kwargs)

    def snapshot(self, model=None, run=None, X=None, Y=None, rename=None, event=None,
                 catcols=None, since=None, ignore_empty=False, groupby=None):
        """
        Take a snapshot of a model and log its metrics, X features and Y targets distribution for later
        drift detection

        Args:
            model (str): the model to snapshot, defaults to the resource given at initialisation
            X (str|pd.DataFrame|np.ndarray): the input data to snapshot
            Y (str|pd.DataFrame|np.ndarray): the target data to snapshot
            rename (dict): a dict that maps columns new -> old, e.g. {'Y_y': 'Y_0'}
            event (str): the event to snapshot, defaults to 'fit' and 'predict'
            run (int|sequence): the experiment's run to snapshot, defaults to all runs
            catcols (list): the columns to treat as categorical
            since (datetime|str): the datetime from which to snapshot X and Y data. If specified,
              X and Y data is collected from all runs since the given datetime, inclusive. If
              'last', the datetime is set to be > last snapshot time.
            groupby (str): group the X, Y datasets by this column before taking the snapshot
            ignore_empty (bool): whether to ignore empty snapshots, if True returns None and
               does not log the snapshot. If False, an AssertionError is raised in case of no data.
               Defaults to False

        Returns:
            dict: the snapshot of metrics, X and Y data, with the following keys
                - info (dict): the snapshot info
                - metrics (dict): the snapshot of model metrics, see DataDriftMonitor.snapshot() for details
                - X (dict): the snapshot of X data, see DataDriftMonitor.snapshot() for details
                - Y (dict): the snapshot of Y data, see DataDriftMonitor.snapshot() for details
        """
        model = model or self._resource
        run = run or '*'
        rename = rename or {}
        if since == 'last':
            since = self._most_recent_snapshot_time()
        snapshots = {}
        snapshots.setdefault('info', self._snapshot_info(model, 'model', run=ensure_list(run), since=since))
        # return snapshot as expected
        # -- if no X or Y, return model snapshot
        # -- if X or Y, return X or Y snapshot
        # -- else return all snapshots as a dict(model=, X=, Y=)
        snapshots.setdefault('metrics', self._snapshot_model_metrics(model, run=run, since=since))
        snapshots.update(self._snapshot_model_xy(model, run=run, X=X, Y=Y, event=event, Xrename=rename.get('X', rename),
                                                 Yrename=rename.get('Y', rename), catcols=catcols, since=since,
                                                 groupby=groupby))
        # log each partial snapshot for this model
        # -- this enables retrieval of partial components by their respective kind (metrics, X, Y)
        partial_snapshots = list(v for k, v in snapshots.items()
                                 if v and k in ('metrics', 'X', 'Y') and v is not None)
        if ignore_empty and not partial_snapshots:
            return
        assert len(partial_snapshots), f'no model events using query {run=} {since=}, cannot take a snapshot'
        for snapshot in partial_snapshots:
            self._log_snapshot(snapshot)
        # -- log the full snapshot
        self._log_snapshot(snapshots)
        return snapshots

    @property
    def data(self):
        """ return snapshots of model metrics, X and Y data

        Returns:
            list[dict]: snapshots of model metrics, X and Y data, with the following keys
                - metrics (dict): the snapshot of model metrics, see DataDriftMonitor.snapshot() for details
                - X (dict): the snapshot of X data, see DataDriftMonitor.snapshot() for details
                - Y (dict): the snapshot of Y data, see DataDriftMonitor.snapshot() for details
        """
        x_mon, y_mon = self._xy_monitor(self._resource)
        metrics_mon = self._metrics_monitor(self._resource)
        snapshots = []
        for i in range(max(len(metrics_mon.data), len(x_mon.data), len(y_mon.data))):
            snapshot = {
                'metrics': metrics_mon.data[i] if i < len(metrics_mon.data) else None,
                'X': x_mon.data[i] if i < len(x_mon.data) else None,
                'Y': y_mon.data[i] if i < len(y_mon.data) else None,
            }
            # combine all snapshots into one, while keeping the details
            merged_snapshot = self._combine_snapshots(snapshot.values())
            snapshot['info'] = merged_snapshot['info']
            snapshot['info']['kind'] = self._kind
            snapshots.append(snapshot)
        return snapshots

    def _xy_monitor(self, model):
        x_mon = DataDriftMonitor(f'{model}', store=self.store, tracking=self.tracking, kind='feature',
                                 query=self._query)
        y_mon = DataDriftMonitor(f'{model}', store=self.store, tracking=self.tracking, kind='label',
                                 query=self._query)
        return x_mon, y_mon

    def _metrics_monitor(self, model):
        return DataDriftMonitor(f'{model}', store=self.store, tracking=self.tracking, kind='metrics',
                                query=self._query)

    def _snapshot_model_metrics(self, model, run=None, since=None):
        metrics_mon = self._metrics_monitor(model)
        run = run if since is None else None
        df: pd.DataFrame = self.tracking.data(run=run, event='metric', kind=None, since=since)
        if df is None or len(df) == 0:
            return
        # reshape events from long to wide format
        # => one row per experiment, run, step, dt
        # => one column per metric (key)
        # => thus we can snapshot metrics as any other numeric data
        index_cols = ['experiment', 'run', 'step', 'dt']
        key_cols = ['key']
        value_cols = ['value']
        df = (pd.pivot_table(df.fillna(1),
                             index=index_cols,
                             columns=key_cols,
                             values=value_cols,
                             dropna=True)
              .droplevel(0, axis=1)
              .reset_index())
        mon_columns = list(set(df.columns) - set(index_cols + key_cols))
        snapshot = metrics_mon._do_snapshot(df, columns=mon_columns, name=str(model), kind='metrics',
                                            info={'run': ensure_list(run)})
        return snapshot

    def _snapshot_model_xy(self, model, run=None, X=None, Y=None, Xrename=None, Yrename=None, event=None, catcols=None,
                           since=None, groupby=None):
        x_mon, y_mon = self._xy_monitor(model)
        event = event or ['fit', 'predict']
        ifElse = lambda v, d: v if v is not None else d
        run = run if since is None else None
        X = ifElse(X, self.tracking.restore_data(run=run, event=event, key='X', since=since))
        Y = ifElse(Y, self.tracking.restore_data(run=run, event=event, key='Y', since=since))
        # TODO document naming convention
        # - tr:resource[run:run,event:event] => tracking for resource with given run, event, key
        Xname = f'tr:{self._resource}[run:{run},event:{event},key:X]'
        Yname = f'tr:{self._resource}[run:{run},event:{event},key:Y]'
        snapshots = {
            'X': tryOr(lambda: x_mon.snapshot(dataset=X, rename=Xrename, kind='feature', prefix='X', name=Xname,
                                              catcols=catcols, groupby=groupby, logged=False), None),
            'Y': tryOr(lambda: y_mon.snapshot(dataset=Y, rename=Yrename, kind='label', prefix='Y', name=Yname,
                                              catcols=catcols, groupby=groupby, logged=False), None),
        }
        return snapshots

    def compare(self, seq=None, d1=None, d2=None, ci=.95, baseline=0, raw=False, matcher=None, since=None):
        """ Measure drift in a model's metrics, X and Y

        Args:
            seq (list|str): sequence of recent predictions to consider,
                use [-i] to refer to the ith last prediction (e.g. [-1]), 'baseline', 'series or 'recent'.
                See DriftMonitorBase.compare() for details
            d1 (pd.DataFrame): the first dataset to compare, optional
            d2 (pd.DataFrame): the second dataset to compare, optional
            ci: confidence interval
            baseline: baseline to compare against
            raw: return raw drift stats or DriftStats object
            matcher (dict): a dict that maps columns new -> old, e.g. {'Y_y': 'Y_0'}
            since (datetime|str): the datetime from which to snapshot X and Y data. If specified,
                X and Y data is collected from all runs since the given datetime, inclusive. If
                'last', the datetime is set to be > last snapshot time. If str is given, it is parsed
                as a datetime string, see .compare() for details.

        Returns:
            DriftStats|[dict]: drift stats or raw drift stats as list of dicts

        See Also:
            - DriftMonitorBase.compare() for details
        """
        metrics_mon = self._metrics_monitor(self._resource)
        x_mon, y_mon = self._xy_monitor(self._resource)
        model_drift = metrics_mon.compare(seq=seq, d1=d1, d2=d2, ci=ci, baseline=baseline, raw=True, matcher=matcher,
                                          since=since)
        x_drift = x_mon.compare(seq=seq, d1=d1, d2=d2, ci=ci, raw=True, matcher=matcher, since=since)
        y_drift = y_mon.compare(seq=seq, d1=d1, d2=d2, ci=ci, raw=True, matcher=matcher, since=since)
        drifts = []
        for s_drift in (model_drift, x_drift, y_drift):
            if isinstance(s_drift, list):
                drifts.extend(s_drift)
            elif s_drift is not None:
                drifts.append(s_drift)
        drifts = drifts[0] if len(drifts) == 1 else drifts
        return drifts if raw else DriftStats(drifts, monitor=self)

    def clear(self, force=False):
        assert force is True, ('force=True required to clear all data from the monitor and its'
                               'underlying experiment log. Note this operation is irreversible.')
        super().clear(force=force)
        x_mon, y_mon = self._xy_monitor(self._resource)
        x_mon.clear(force=force)
        y_mon.clear(force=force)
