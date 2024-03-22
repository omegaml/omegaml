import pandas as pd

from omegaml.backends.monitoring.base import DriftMonitorBase
from omegaml.backends.monitoring.datadrift import DataDriftMonitor
from omegaml.backends.monitoring.stats import DriftStats


class ModelDriftMonitor(DriftMonitorBase):
    def __init__(self, model=None, tracking=None, store=None):
        super().__init__(resource=model, store=store, tracking=tracking)

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

    def drift(self, seq=None, d1=None, d2=None, ci=.95, baseline=0, raw=False):
        """ Measure drift in the model, X and Y

        Args:
            seq: sequence of recent predictions to consider
            d1: sequence of recent predictions to consider
            d2: sequence of recent predictions to consider
            ci: confidence interval
            baseline: baseline to compare against
            raw: return raw drift stats or DriftStats object

        Returns:
            DriftStats|[dict]: drift stats or raw drift stats as list of dicts

        See Also:
            - DriftMonitorBase.drift for details
        """
        model_drift = super().drift(seq=seq, d1=d1, d2=d2, ci=ci, baseline=baseline, raw=True)
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
