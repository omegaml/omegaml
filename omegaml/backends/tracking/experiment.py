import os

from omegaml.backends.basemodel import BaseModelBackend
from omegaml.backends.tracking.base import TrackingProvider


class ExperimentBackend(BaseModelBackend):
    """ ExperimentBackend provides storage of tracker configurations

    Usage:

        To log metrics and other data::

            with om.runtime.experiment('myexp') as exp:
                om.runtime.model('mymodel').fit(X, Y)
                om.runtime.model('mymodel').score(X, Y) # automatically log score result
                exp.log_metric('mymetric', value)
                exp.log_param('myparam', value)
                exp.log_artifact(X, 'X')
                exp.log_artifact(Y, 'Y')
                exp.log_artifact(om.models.metadata('mymodel'), 'mymodel')

        To log data and automatically profile system data::

            with om.runtime.experiment('myexp', provider='profiling') as exp:
                om.runtime.model('mymodel').fit(X, Y)
                om.runtime.model('mymodel').score(X, Y) # automatically log score result
                exp.log_metric('mymetric', value)
                exp.log_param('myparam', value)
                exp.log_artifact(X, 'X')
                exp.log_artifact(Y, 'Y')
                exp.log_artifact(om.models.metadata('mymodel'), 'mymodel')

            # profiling data contains metrics for cpu, memory and disk use
            data = exp.data(event='profile')

        To get back experiment data without running an experiment::

            # recommended way
            exp = om.runtime.experiment('myexp').use()
            exp_df = exp.data()

            # experiments exist in the models store
            exp = om.models.get('experiments/myexp')
            exp_df = exp.data()

    See Also:

        * :class:`omegaml.backends.tracking.OmegaSimpleTracker`
        * :class:`omegaml.backends.tracking.OmegaProfilingTracker`
    """
    KIND = 'experiment.tracker'
    exp_prefix = 'experiments/'

    @classmethod
    def supports(self, obj, name, **kwargs):
        return isinstance(obj, TrackingProvider)

    def put(self, obj, name, **kwargs):
        name = f'{self.exp_prefix}{name}' if not name.startswith(self.exp_prefix) else name
        # FIXME use proper pickle magic to avoid storing the store
        store = obj._store
        obj._store = None
        obj._model_store = None
        meta = super().put(obj, name, **kwargs)
        meta.attributes.setdefault('tracking', {})
        meta.attributes['tracking']['dataset'] = obj._data_name
        meta.save()
        obj._store = store
        obj._model_store = self.model_store
        return meta

    def get(self, name, raw=False, data_store=None, **kwargs):
        assert data_store is not None, "experiments require a datastore, specify data_store=om.datasets"
        tracker = super().get(name, **kwargs)
        name = os.path.basename(name)
        tracker._store = data_store
        tracker._model_store = self.model_store
        return tracker.experiment(name) if not raw else tracker

    def drop(self, name, force=False, version=-1, data_store=None, **kwargs):
        data_store = data_store or self.data_store
        meta = self.model_store.metadata(name)
        dataset = meta.attributes.get('tracking', {}).get('dataset')
        data_store.drop(dataset, force=True) if dataset else None
        return self.model_store._drop(name, force=force, version=version, **kwargs)
