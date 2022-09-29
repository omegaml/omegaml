import os

from omegaml import load_class
from omegaml.util import SystemPosixPath


class OmegaTrackingProxy:
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
    """
    # test support, does not actually track nesting
    __nested = 0

    def __init__(self, experiment=None, provider=None, runtime=None, implied_run=True):
        self.runtime = runtime
        self.provider = provider
        self._experiment = experiment
        self._implied_run = implied_run
        self._with_experiment = None
        self._tracker = None

    def __getattr__(self, item):
        if hasattr(self.experiment, item):
            return getattr(self.experiment, item)
        return super().__getattribute__(item)

    def create_experiment(self, name, *args, provider=None, **kwargs):
        om = self.runtime.omega
        provider = provider or 'default'
        trackercls = load_class(om.defaults.OMEGA_TRACKING_PROVIDERS.get(provider))
        tracker = trackercls(name, *args, store=om.datasets, model_store=om.models, **kwargs)
        meta = om.models.put(tracker, name, noversion=True)
        return tracker.experiment(name)

    @property
    def experiment(self):
        from omegaml.backends.experiment import ExperimentBackend

        if self._tracker is None:
            om = self.runtime.omega
            fqdn = SystemPosixPath(ExperimentBackend.exp_prefix) / self._experiment
            exp = (om.models.get(str(fqdn), data_store=om.datasets) or
                   self.create_experiment(self._experiment, provider=self.provider))
            self._tracker = exp
        return self._tracker

    def __enter__(self):
        # specify a permanent task argument
        OmegaTrackingProxy.__nested += 1
        self.runtime.require(task=dict(__experiment=self._experiment), always=True)
        self._with_experiment = experiment = self.experiment
        no_active_run = experiment.status() in ('STOPPED', 'PENDING')
        if self._implied_run or no_active_run:
            experiment.start()
            self._implied_run = True if no_active_run else self._implied_run
        return experiment

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._implied_run:
            experiment = self._with_experiment or self.experiment
            experiment.stop()
        self._with_experiment = None
        OmegaTrackingProxy.__nested -= 1
        # remove task argument
        if OmegaTrackingProxy.__nested == 0:
            self.runtime.require(task=dict(__experiment=None), always=True)
