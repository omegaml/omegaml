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
                 catcols=None, since=None, ignore_empty=False):
        """
        Take a snapshot of a model and log its metrics, X features and Y targets distribution for later
        drift detection

        Args:
            model (str): the model to snapshot
            X (str|pd.DataFrame|np.ndarray): the input data to snapshot
            Y (str|pd.DataFrame|np.ndarray): the target data to snapshot
            rename (dict): a dict that maps columns new -> old, e.g. {'Y_y': 'Y_0'}
            event (str): the event to snapshot, defaults to 'fit' and 'predict'
            run (int|sequence): the experiment's run to snapshot, defaults to all runs
            catcols (list): the columns to treat as categorical
            since (datetime|str): the datetime from which to snapshot X and Y data. If specified,
              X and Y data is collected from all runs since the given datetime, inclusive. If
              'last', the datetime is set to be > last snapshot time.
            ignore_empty (bool): whether to ignore empty snapshots, if True returns None and
               does not log the snapshot. If False, an AssertionError is raised in case of no data.
               Defaults to False

        Returns:
            dict: the snapshot
        """
        # what do we snapshot?
        # - validation metric (accuracy, f1, f2, confusion matrix etc)
        # - data input distribution (i.e. training/validation X)
        # - (expected) label distribution (Y)
        # NEXT:
        # - track labels (Y)
        # - track inputs (X)
        # - metrics, Y and X should also be possible to override via kwargs (instead of taking from tracking)
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
                                                 Yrename=rename.get('Y', rename), catcols=catcols, since=since))
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

    def _xy_monitor(self, model):
        x_mon = DataDriftMonitor(f'{model}', store=self.store, tracking=self.tracking, kind='feature')
        y_mon = DataDriftMonitor(f'{model}', store=self.store, tracking=self.tracking, kind='label')
        return x_mon, y_mon

    def _metrics_monitor(self, model):
        return DataDriftMonitor(f'{model}', store=self.store, tracking=self.tracking, kind='metrics')

    def _snapshot_model_metrics(self, model, run=None, since=None):
        metrics_mon = self._metrics_monitor(model)
        run = run if since is None else None
        df: pd.DataFrame = self.tracking.data(run=run, event='metric', kind=None, since=since)
        if df is None or len(df) == 0:
            return
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
        snapshot = metrics_mon._do_snapshot(df, columns=mon_columns, name=str(model), kind='metrics',
                                            info={'run': ensure_list(run)})
        return snapshot

    def _snapshot_model_xy(self, model, run=None, X=None, Y=None, Xrename=None, Yrename=None, event=None, catcols=None,
                           since=None):
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
            'X': tryOr(lambda: x_mon._do_snapshot(self._assert_dataframe(X, rename=Xrename),
                                                  kind='feature', _prefix='X', name=Xname, catcols=catcols), None),
            'Y': tryOr(lambda: y_mon._do_snapshot(self._assert_dataframe(Y, rename=Yrename),
                                                  kind='label', _prefix='Y', name=Yname, catcols=catcols), None),
        }
        return snapshots

    def compare(self, seq=None, d1=None, d2=None, ci=.95, baseline=0, raw=False, matcher=None, since=None):
        """ Measure drift in a model's metrics, X and Y

        Args:
            seq: sequence of recent predictions to consider
            d1: sequence of recent predictions to consider
            d2: sequence of recent predictions to consider
            ci: confidence interval
            baseline: baseline to compare against
            raw: return raw drift stats or DriftStats object
            matcher (dict): a dict that maps columns new -> old, e.g. {'Y_y': 'Y_0'}

        Returns:
            DriftStats|[dict]: drift stats or raw drift stats as list of dicts

        See Also:
            - DriftMonitorBase.drift for details
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
        super().clear(force=force)
        x_mon, y_mon = self._xy_monitor(self._resource)
        x_mon.clear(force=force)
        y_mon.clear(force=force)
