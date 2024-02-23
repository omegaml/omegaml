import os

from omegaml import load_class
from omegaml.runtimes.proxies.baseproxy import RuntimeProxyBase
from omegaml.util import SystemPosixPath


class OmegaTrackingProxy(RuntimeProxyBase):
    """ OmegaTrackingProxy provides the runtime context for experiment tracking

    Usage:

        Using implied start()/stop() semantics, creating experiment runs::

            with om.runtime.experiment('myexp') as exp:
                ...
                exp.log_metric('accuracy', score)


        Using explicit start()/stop() semantics::

            exp = om.runtime.experiment('myexp')
            exp.start()
            ...
            exp.stop()

    See Also:

        * OmegaSimpleTracker
        * ExperimentBackend

    .. versionchanged:: 0.17
          with om.runtime.experiment() now returns the OmegaTrackingProxy instance
          instead of the underlying TrackingProvider
    """

    def __init__(self, experiment=None, provider=None, runtime=None, implied_run=True,
                 recreate=False, **tracker_kwargs):
        self.provider = provider
        self._experiment = experiment
        self._implied_run = implied_run
        self._with_experiment = None
        self._tracker = None
        self._tracker_kwargs = tracker_kwargs
        self._recreate = recreate
        super().__init__(experiment, runtime=runtime)

    def _apply_require(self):
        # require is not applicable for experiments, as it is implied with the model/script/job
        pass

    def __getattr__(self, item):
        if hasattr(self.experiment, item):
            return getattr(self.experiment, item)
        return super().__getattribute__(item)

    def create_experiment(self, name, *args, provider=None, **kwargs):
        from omegaml.backends.tracking.experiment import ExperimentBackend
        om = self.runtime.omega
        provider = provider or 'default'
        trackercls = load_class(om.defaults.OMEGA_TRACKING_PROVIDERS.get(provider))
        tracker = trackercls(name, *args, store=om.datasets, model_store=om.models, **kwargs)
        # kind= forces use of ExperimentBackend for the case where
        #       the experiment name is the same as an existing object that is not an experiment
        meta = om.models.put(tracker, name,
                             kind=ExperimentBackend.KIND,
                             noversion=True)
        return tracker.experiment(name)

    @property
    def experiment(self):
        from omegaml.backends.tracking.experiment import ExperimentBackend

        if self._tracker is None:
            om = self.runtime.omega
            fqdn = SystemPosixPath(ExperimentBackend.exp_prefix) / self._experiment
            if self._recreate:
                om.models.drop(str(fqdn), force=True)
                self._recreate = False
            exp = (om.models.get(str(fqdn), data_store=om.datasets) or
                   self.create_experiment(self._experiment, provider=self.provider, **self._tracker_kwargs))
            self._tracker = exp
        return self._tracker

    def __enter__(self):
        # specify a permanent task argument
        self.runtime.require(task=dict(__experiment=self._experiment), always=True)
        self._with_experiment = experiment = self.experiment
        no_active_run = experiment.status() in ('STOPPED', 'PENDING')
        if self._implied_run or no_active_run:
            experiment.start()
            self._implied_run = True if no_active_run else self._implied_run
        experiment.start_runtime()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        experiment = self._with_experiment or self.experiment
        experiment.stop_runtime()
        if self._implied_run:
            experiment.stop()
        self._with_experiment = None
        # remove task argument
        self.runtime.require(task=dict(__experiment=None), always=True)
