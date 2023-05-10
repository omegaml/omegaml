import getpass

from omegaml import settings


class TrackingProvider:
    """ TrackingProvider implements an abstract interface to experiment tracking

    Concrete implementations like MLFlow, Sacred or Neptune.ai can be implemented
    based on TrackingProvider. In combination with the runtime's OmegaTrackingProxy
    this provides a powerful tracking interface that scales with your needs.

    How it works:

        1. Experiments created using ``om.runtime.experiment()`` are stored as
           instances of a TrackingProvider concrete implementation

        2. Upon retrieval of an experiment, any call to its API is proxied to the
           actual implementation, e.g. MLFlow

        3. On calling a model method via the runtime, e.g. ``om.runtime.model().fit()``,
           the TrackingProvider information is passed on to the runtime worker,
           and made available as the backend.tracking property. Thus within a
           model backend, you can always log to the tracker by using::

                with self.tracking as exp:
                    exp.log_metric() # call any TrackingProvider method

        4. omega-ml provides the OmegaSimpleTracker, which implements a tracking
           interface similar to packages like MLFlow, Sacred. See ExperimentBackend
           for an example.
    """

    def __init__(self, experiment, store=None, model_store=None):
        self._experiment = experiment
        self._run = None
        self._store = store
        self._model_store = model_store
        self._extra_log = None

    def __repr__(self):
        return f"{self.__class__.__name__}({self._experiment})"

    @property
    def userid(self):
        defaults = getattr(self._store, 'defaults', None) or settings()
        return getattr(defaults, 'OMEGA_USERID', getpass.getuser())

    def experiment(self, name=None):
        self._experiment = name or self._experiment
        return self

    def track(self, obj, store=None, label=None):
        """ attach this experiment to the named object

        Usage:

            # use in experiment context
            with om.runtime.experiment('myexp') as exp:
                exp.track('mymodel')

            # use on experiment directly
            exp = om.runtime.experiment('myexp')
            exp.track('mymodel')

        Args:
                obj (str): the name of the object
                store (OmegaStore): optional, om.models, om.scripts, om.jobs.
                    If not provided will use om.models
                label (str): optional, the label of the worker, default is
                    'default'

        Note:
                This modifies the object's metadata.attributes::

                    { 'tracking': { label: self._experiment } }
        """
        label = label or 'default'
        store = store or self._model_store
        meta = store.metadata(obj)
        store.link_experiment(obj, self._experiment, label=label)
        meta.save()
        return meta

    def active_run(self):
        self._run = (self._run or 0) + 1
        return self._run

    def status(self, run=None):
        return 'STOPPED'

    def start(self, run=None):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def start_runtime(self):
        # hook to signal the runtime is starting a task inside a worker
        # this is unlike the .start() method which is called to start a run
        # which can happen in the client or in the runtime
        pass

    def stop_runtime(self):
        # hook to signal the runtime has completed a task inside a worker
        # this is unlike the .stop() method which is called to stop a run
        # which can happen in the client or in the runtime
        self.flush()

    def log_event(self, event, key, value, step=None, **extra):
        raise NotImplementedError

    def log_metric(self, key, value, step=None, **extra):
        raise NotImplementedError

    def log_artifact(self, obj, name, step=None, **extra):
        raise NotImplementedError

    def log_param(self, key, value, step=None, **extra):
        raise NotImplementedError

    def log_extra(self, remove=False, **kwargs):
        # add extra logging information for every subsequent log_xyz call
        raise NotImplementedError

    def tensorflow_callback(self):
        from omegaml.backends.tracking import TensorflowCallback
        return TensorflowCallback(self)

    def data(self, experiment=None, run=None, event=None, step=None, key=None, raw=False):
        raise NotImplementedError

    def flush(self):
        pass

    @property
    def _data_name(self):
        return f'.experiments/{self._experiment}'
