import getpass
import logging

from omegaml import settings, load_class

logger = logging.getLogger(__name__)


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

    def __init__(self, experiment, store=None, model_store=None, autotrack=False):
        self._experiment = experiment
        self._run = None
        self._store = store
        self._model_store = model_store
        self._extra_log = None
        self._autotrack = autotrack

    def __repr__(self):
        return f"{self.__class__.__name__}({self._experiment})"

    @property
    def userid(self):
        defaults = getattr(self._store, 'defaults', None) or settings()
        return getattr(defaults, 'OMEGA_USERID', getpass.getuser())

    @property
    def autotrack(self):
        return self._autotrack

    @autotrack.setter
    def autotrack(self, value):
        self._autotrack = value

    def experiment(self, name=None):
        self._experiment = name or self._experiment
        return self

    def track(self, obj, store=None, label=None, monitor=False, monitor_kwargs=None, **kwargs):
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
                monitor (bool|str): optional, truthy sets up a monitor to track
                    drift in the object, if a string is provided it is used as
                    the monitoring provider
                monitor_kwargs (dict): optional, additional keyword arguments
                    to pass to the monitor

        Note:
                This modifies the object's metadata.attributes::

                    { 'tracking': { label: self._experiment } }

                If monitor is set, a monitor definition is added to the object's metadata::

                    { 'tracking': { 'monitors': [ { 'experiment': self._experiment,
                                       'provider': monitor } ] } }
        """
        label = label or 'default'
        store = store or self._model_store
        meta = store.metadata(obj)
        assert meta is not None, f"{obj} does not exist in {store}"
        store.link_experiment(obj, self._experiment, label=label)
        if monitor:
            monitor_kwargs = monitor_kwargs or kwargs
            monitor_provider = monitor if isinstance(monitor, str) else None
            self.as_monitor(obj, store=store, provider=monitor_provider, **monitor_kwargs)
        meta.save()
        return meta

    def as_monitor(self, obj, alerts=None, schedule=None, store=None, provider=None, **kwargs):
        """
        Return and attach a drift monitor to this experiment

        Args:
            obj (str): the name of the model
            alerts (list): a list of alert definitions. Each alert definition is a dict
                with keys 'event', 'recipients'. 'event' is the event to get from the
                tracking log, 'recipients' is a list of recipients (e.g. email address,
                notification channel)
            schedule (str): the job scheduling interval for the monitoring job, as used
                in om.jobs.schedule() when the job is created
            store (OmegaStore): the store to use, defaults to self._model_store
            provider (str): the name of the monitoring provider, defaults to store.prefix

        Returns:
            monitor (DriftMonitor): a drift monitor for the object
        """
        store = store or self._model_store
        mon = self._has_monitor(obj, store=store)
        is_autotracked = getattr(self, 'autotrack', False)
        if not is_autotracked:
            logger.warning(
                f"Experiment {self._experiment} is not autotracked, model calls are not tracked automatically")
        provider = provider or mon.get('provider') if mon else None
        provider = provider or store.prefix.replace('/', '')
        store.link_monitor(obj, self._experiment, provider=provider, alerts=alerts, schedule=schedule)
        self._create_monitor_job(obj, model_store=store)
        ProviderClass = load_class(store.defaults.OMEGA_MONITORING_PROVIDERS.get(provider))
        return ProviderClass(obj, tracking=self, store=store, **kwargs)

    def _create_monitor_job(self, obj, model_store=None, jobs_store=None):
        """
        Ensure monitors are created for a model

        This creates a job for each monitor definition in the model's metadata. The job
        will run at the specified interval and capture the model's state and drift.
        Alerts are sent to the recipients specified in the monitor definition. If a job
        already exists it is not created again.

        The name of the job is derived from the model's name and the experiment's name in
        the form 'monitors/{experiment}/{modelname}'. The schedule is set to 'daily'
        unless specified in the monitor definition in

        Args:
            obj (str): the name of the model
            model_store (OmegaStore): the store to use, defaults to self._model_store
            jobs_store (OmegaJobs): the jobs store to use, defaults to om.jobs

        Returns:
            list of jobs created as [Metadata, ...]
        """
        # create and schedule a monitoring job for the object
        # -- assumes the object has a monitor definition
        # -- the experiment associated with the monitor must be autotracked
        # -- if the job does not exist yet, create it
        # -- if the job exists, do nothing
        # Returns: list of jobs created as [Metadata, ...]
        import omegaml as om
        store = model_store or self._model_store
        jobs = jobs_store or om.jobs
        code_block = self._monitor_job_template()
        meta = store.metadata(obj)
        tracking = meta.attributes.setdefault('tracking', {})
        monitors = tracking.setdefault('monitors', [])
        jobs_created = []
        for mon in monitors:
            experiment = mon['experiment']
            provider = mon['provider']
            jobname = mon.get('job') or f'monitors/{experiment}/{meta.name}'
            schedule = mon.get('schedule', 'daily')
            alerts = mon.get('alerts', [])
            if not jobs.list(jobname):
                # if job does not exist yet create it
                code = code_block.format(**locals())
                job_meta = jobs.create(code, jobname)
                jobs.schedule(jobname, schedule)
                mon['job'] = jobname
                mon['schedule'] = schedule
                meta.save()
                jobs_created.append(job_meta)
        return jobs_created

    def _monitor_job_template(self):
        code_block = """
        # configure
        import omegaml as om
        # -- the name of the experiment
        experiment = '{experiment}'
        # -- the name of the model
        name = '{meta.name}'
        # -- the name of the monitoring provider
        provider = '{provider}'
        # -- the alert rules
        alerts = {alerts}
        # snapshot recent state and capture drift 
        with om.runtime.model(name).experiment(experiment) as exp:
            mon = exp.as_monitor(name, store=om.models, provider=provider)
            mon.snapshot(since='last', ignore_empty=True) 
            mon.capture(rules=alerts, since='last')
        """
        return code_block

    def _has_monitor(self, obj, store=None):
        store = store or self._model_store
        meta = store.metadata(obj)
        monitors = meta.attributes.setdefault('tracking', {}).setdefault('monitors', [])
        for mon in monitors:
            if mon.get('experiment') == self._experiment:
                return mon
        return None

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

    def log_data(self, key, data, step=None, **extra):
        raise NotImplementedError

    def tensorflow_callback(self):
        from omegaml.backends.tracking import TensorflowCallback
        return TensorflowCallback(self)

    def data(self, experiment=None, run=None, event=None, step=None, key=None, raw=False, **query):
        raise NotImplementedError

    def clear(self, force=False):
        raise NotImplementedError

    def flush(self):
        pass

    @property
    def _data_name(self):
        return f'.experiments/{self._experiment}'
