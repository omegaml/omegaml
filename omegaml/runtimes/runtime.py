from __future__ import absolute_import

import logging
from celery import Celery

logger = logging.getLogger(__name__)


class CeleryTask(object):
    """
    A thin wrapper for a Celery.Task object

    This is so that we can collect common delay arguments on the
    .task() call
    """

    def __init__(self, task, kwargs):
        """

        Args:
            task (Celery.Task): the celery task object
            kwargs (dict): optional, the kwargs to pass to apply_async
        """
        self.task = task
        self.kwargs = dict(kwargs)

    def _apply_kwargs(self, task_kwargs, celery_kwargs):
        # update task_kwargs from runtime's passed on kwargs
        # update celery_kwargs to match celery routing semantics
        task_kwargs.update(self.kwargs.get('task', {}))
        celery_kwargs.update(self.kwargs.get('routing', {}))
        if 'label' in celery_kwargs:
            celery_kwargs['queue'] = celery_kwargs['label']
            del celery_kwargs['label']

    def apply_async(self, args=None, kwargs=None, **celery_kwargs):
        """

        Args:
            args (tuple): the task args
            kwargs (dict): the task kwargs
            celery_kwargs (dict): apply_async kwargs, e.g. routing

        Returns:
            AsyncResult
        """
        self._apply_kwargs(kwargs, celery_kwargs)
        return self.task.apply_async(args=args, kwargs=kwargs, **celery_kwargs)

    def delay(self, *args, **kwargs):
        """
        submit the task with args and kwargs to pass on

        This calls task.apply_async and passes on the self.kwargs.
        """
        return self.apply_async(args=args, kwargs=kwargs)

    def signature(self, args=None, kwargs=None, immutable=False, **celery_kwargs):
        """ return the task signature with all kwargs and celery_kwargs applied
        """
        self._apply_kwargs(kwargs, celery_kwargs)
        sig = self.task.signature(args=args, kwargs=kwargs, **celery_kwargs, immutable=immutable)
        return sig

    def run(self, *args, **kwargs):
        return self.delay(*args, **kwargs)


class OmegaRuntime(object):
    """
    omegaml compute cluster gateway
    """

    def __init__(self, omega, bucket=None, defaults=None, celeryconf=None):
        from omegaml.util import settings

        self.omega = omega
        defaults = defaults or settings()
        self.bucket = bucket
        self.pure_python = getattr(defaults, 'OMEGA_FORCE_PYTHON_CLIENT', False)
        self.pure_python = self.pure_python or self._client_is_pure_python()
        # initialize celery as a runtimes
        taskpkgs = defaults.OMEGA_CELERY_IMPORTS
        celeryconf = celeryconf or defaults.OMEGA_CELERY_CONFIG
        # ensure we use current value
        celeryconf['CELERY_ALWAYS_EAGER'] = bool(defaults.OMEGA_LOCAL_RUNTIME)
        self.celeryapp = Celery('omegaml')
        self.celeryapp.config_from_object(celeryconf)
        # needed to get it to actually load the tasks
        # https://stackoverflow.com/a/35735471
        self.celeryapp.autodiscover_tasks(taskpkgs, force=True)
        self.celeryapp.finalize()
        # temporary requirements, use .require() to set
        self._require_kwargs = dict(task={}, routing={})
        # fixed default arguments, use .require(always=True) to set
        self._task_default_kwargs = dict(task={}, routing={})
        # default routing label
        self._default_label = self.celeryapp.conf.get('CELERY_DEFAULT_QUEUE')

    def __repr__(self):
        return 'OmegaRuntime({})'.format(self.omega.__repr__())

    @property
    def auth(self):
        return None

    @property
    def _common_kwargs(self):
        common = dict(self._task_default_kwargs)
        common['task'].update(pure_python=self.pure_python, __bucket=self.bucket)
        common['task'].update(self._require_kwargs['task'])
        common['routing'].update(self._require_kwargs['routing'])
        return common

    @property
    def _inspect(self):
        return self.celeryapp.control.inspect()

    def mode(self, local=None, logging=None):
        """ specify runtime modes

        Args:
            local (bool): if True, all execution will run locally, else on
               the configured remote cluster
            logging (bool|str|tuple): if True, will set the root logger output
               at INFO level; a single string is the name of the logger,
               typically a module name; a tuple (logger, level) will select
               logger and the level. Valid levels are INFO, WARNING, ERROR,
               CRITICAL, DEBUG

        Usage:
            # run all runtime tasks locally
            om.runtime.mode(local=True)

            # enable logging both in local and remote mode
            om.runtime.mode(logging=True)

            # select a specific module and level)
            om.runtime.mode(logging=('sklearn', 'DEBUG'))

            # disable logging
            om.runtime.mode(logging=False)
        """
        if local is not None:
            self.celeryapp.conf['CELERY_ALWAYS_EAGER'] = local
        self._task_default_kwargs['task']['__logging'] = logging
        return self

    def _client_is_pure_python(self):
        try:
            import pandas as pd
            import numpy as np
            import sklearn
        except Exception as e:
            logging.getLogger().info(e)
            return True
        else:
            return False

    def _sanitize_require(self, value):
        # convert value into dict(label=value)
        if isinstance(value, str):
            return dict(label=value)
        if isinstance(value, (list, tuple)):
            return dict(*value)
        return value

    def require(self, label=None, always=False, routing=None, task=None, **kwargs):
        """
        specify requirements for the task execution

        Use this to specify resource or routing requirements on the next task
        call sent to the runtime. Any requirements will be reset after the
        call has been submitted.

        Args:
            always (bool): if True requirements will persist across task calls. defaults to False
            label (str): the label required by the worker to have a runtime task dispatched to it
            task (dict): if specified applied to the task kwargs
            kwargs: requirements specification that the runtime understands

        Usage:
            om.runtime.require(label='gpu').model('foo').fit(...)

        Returns:
            self
        """
        routing = routing or {
            'label': label or self._default_label
        }
        task = task or {}
        if always:
            self._task_default_kwargs['routing'].update(routing)
            self._task_default_kwargs['task'].update(task)
        else:
            self._require_kwargs['routing'].update(routing)
            self._require_kwargs['task'].update(task)
        return self

    def model(self, modelname, require=None):
        """
        return a model for remote execution

        Args:
            require (dict): routing requirements for this job
        """
        from omegaml.runtimes.modelproxy import OmegaModelProxy
        self.require(**self._sanitize_require(require)) if require else None
        return OmegaModelProxy(modelname, runtime=self)

    def job(self, jobname, require=None):
        """
        return a job for remote exeuction

        Args:
            require (dict): routing requirements for this job
        """
        from omegaml.runtimes.jobproxy import OmegaJobProxy

        self.require(**self._sanitize_require(require)) if require else None
        return OmegaJobProxy(jobname, runtime=self)

    def script(self, scriptname, require=None):
        """
        return a script for remote execution

        Args:
            require (dict): routing requirements for this job
        """
        from omegaml.runtimes.scriptproxy import OmegaScriptProxy

        self.require(**self._sanitize_require(require)) if require else None
        return OmegaScriptProxy(scriptname, runtime=self)

    def experiment(self, experiment, provider=None, implied_run=True):
        """ set the tracking backend and experiment

        Args:
            experiment (str): the name of the experiment
            provider (str): the name of the provider
        """
        from omegaml.runtimes.trackingproxy import OmegaTrackingProxy
        # tracker implied_run means we are using the currently active run, i.e. with block will call exp.start()
        tracker = OmegaTrackingProxy(experiment, provider=provider, runtime=self, implied_run=implied_run)
        return tracker

    def task(self, name):
        """
        retrieve the task function from the celery instance

        Args:
            kwargs (dict): routing keywords to CeleryTask.apply_async
        """
        taskfn = self.celeryapp.tasks.get(name)
        assert taskfn is not None, "cannot find task {name} in Celery runtime".format(**locals())
        task = CeleryTask(taskfn, self._common_kwargs)
        self._require_kwargs = dict(routing={}, task={})
        return task

    def settings(self, require=None):
        """
        return the runtimes's cluster settings
        """
        self.require(**require) if require else None
        return self.task('omegaml.tasks.omega_settings').delay().get()

    def ping(self, *args, require=None, wait=True, **kwargs):
        """
        ping the runtimes

        Args:
            require (dict): routing requirements for this job
            args (tuple): task args
            kwargs (dict): task kwargs
        """
        self.require(**require) if require else None
        promise = self.task('omegaml.tasks.omega_ping').delay(*args, **kwargs)
        return promise.get() if wait else promise

    def enable_hostqueues(self):
        """ enable a worker-specific queue on every worker host

        Returns:

        """
        control = self.celeryapp.control
        inspect = control.inspect()
        active = inspect.active()
        queues = []
        for worker in active.keys():
            hostname = worker.split('@')[-1]
            control.cancel_consumer(hostname)
            control.add_consumer(hostname, destination=[worker])
            queues.append(hostname)
        return queues

    def workers(self):
        """ list of workers

        Returns:
            dict of workers => list of active tasks

        See Also:
            celery Inspect.active()
        """
        return self._inspect.active()

    def queues(self):
        """ list queues

        Returns:
            dict of workers => list of queues

        See Also:
            celery Inspect.active_queues()
        """
        return self._inspect.active_queues()

    def stats(self):
        """ worker statistics

        Returns:
            dict of workers => dict of stats

        See Also:
            celery Inspect.stats()
        """
        return self._inspect.stats()

    def callback(self, script_name, always=False, **kwargs):
        """ Add a callback to a registered script

        The callback will be triggered upon successful or failed
        execution of the runtime tasks. The script syntax is:

        # script.py
        def run(om, state=None, result=None, **kwargs):
            # state (str): 'SUCCESS'|'ERROR'
            # result (obj): the task's serialized result

        Args:
            script_name (str): the name of the script (in om.scripts)
            always (bool): if True always apply this callback, defaults to False
            **kwargs: and other kwargs to pass on to the script

        Returns:
            self
        """
        success_sig = (self.script(script_name)
                       .task(as_callback=True)
                       .signature(args=['SUCCESS', script_name],
                                  kwargs=kwargs,
                                  immutable=False))
        error_sig = (self.script(script_name)
                     .task(as_callback=True)
                     .signature(args=['ERROR', script_name],
                                kwargs=kwargs,
                                immutable=False))

        if always:
            self._task_default_kwargs['routing']['link'] = success_sig
            self._task_default_kwargs['routing']['link_error'] = error_sig
        else:
            self._require_kwargs['routing']['link'] = success_sig
            self._require_kwargs['routing']['link_error'] = error_sig
        return self


# apply mixins
from omegaml.runtimes.mixins.taskcanvas import canvas_chain, canvas_group, canvas_chord

OmegaRuntime.sequence = canvas_chain
OmegaRuntime.parallel = canvas_group
OmegaRuntime.mapreduce = canvas_chord
