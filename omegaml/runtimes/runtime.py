from __future__ import absolute_import

import logging
from celery import Celery
from celery.events import EventReceiver
from copy import deepcopy
from socket import gethostname

from omegaml.mongoshim import mongo_url
from omegaml.util import dict_merge

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

    def _apply_auth(self, args, kwargs, celery_kwargs):
        from omegaml.client.auth import AuthenticationEnv
        AuthenticationEnv.active().taskauth(args, kwargs, celery_kwargs)

    def apply_async(self, args=None, kwargs=None, **celery_kwargs):
        """

        Args:
            args (tuple): the task args
            kwargs (dict): the task kwargs
            celery_kwargs (dict): apply_async kwargs, e.g. routing

        Returns:
            AsyncResult
        """
        args = args or tuple()
        kwargs = kwargs or {}
        self._apply_kwargs(kwargs, celery_kwargs)
        self._apply_auth(args, kwargs, celery_kwargs)
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
        self._create_celery_app(defaults, celeryconf=celeryconf)
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
        common = deepcopy(self._task_default_kwargs)
        common['task'].update(pure_python=self.pure_python, __bucket=self.bucket)
        common['task'].update(self._require_kwargs['task'])
        common['routing'].update(self._require_kwargs['routing'])
        return common

    @property
    def _inspect(self):
        return self.celeryapp.control.inspect()

    @property
    def is_local(self):
        return self.celeryapp.conf['CELERY_ALWAYS_EAGER']

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

        Usage::

            # run all runtime tasks locally
            om.runtime.mode(local=True)

            # enable logging both in local and remote mode
            om.runtime.mode(logging=True)

            # select a specific module and level)
            om.runtime.mode(logging=('sklearn', 'DEBUG'))

            # disable logging
            om.runtime.mode(logging=False)
        """
        if isinstance(local, bool):
            self.celeryapp.conf['CELERY_ALWAYS_EAGER'] = local
        self._task_default_kwargs['task']['__logging'] = logging
        return self

    def _create_celery_app(self, defaults, celeryconf=None):
        # initialize celery as a runtimes
        taskpkgs = defaults.OMEGA_CELERY_IMPORTS
        celeryconf = dict(celeryconf or defaults.OMEGA_CELERY_CONFIG)
        # ensure we use current value
        celeryconf['CELERY_ALWAYS_EAGER'] = bool(defaults.OMEGA_LOCAL_RUNTIME)
        if celeryconf['CELERY_RESULT_BACKEND'].startswith('mongodb://'):
            celeryconf['CELERY_RESULT_BACKEND'] = mongo_url(self.omega, drop_kwargs=['uuidRepresentation'])
        # initialize ssl configuration
        if celeryconf.get('BROKER_USE_SSL'):
            # celery > 5 requires ssl options to be specific
            # https://docs.celeryq.dev/en/stable/userguide/configuration.html#std-setting-broker_use_ssl
            # https://github.com/celery/kombu/issues/1493
            # https://docs.python.org/dev/library/ssl.html#ssl.wrap_socket
            # https://www.openssl.org/docs/man3.0/man3/SSL_CTX_set_default_verify_paths.html
            # env variables:
            # SSL_CERT_FILE, CA_CERTS_PATH
            self._apply_broker_ssl(celeryconf)
        self.celeryapp = Celery('omegaml')
        self.celeryapp.config_from_object(celeryconf)
        # needed to get it to actually load the tasks
        # https://stackoverflow.com/a/35735471
        self.celeryapp.autodiscover_tasks(taskpkgs, force=True)
        self.celeryapp.finalize()

    def _apply_broker_ssl(self, celeryconf):
        # hook to apply broker ssl options
        pass

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

    def require(self, label=None, always=False, routing=None, task=None,
                logging=None, override=True, **kwargs):
        """
        specify requirements for the task execution

        Use this to specify resource or routing requirements on the next task
        call sent to the runtime. Any requirements will be reset after the
        call has been submitted.

        Args:
            always (bool): if True requirements will persist across task calls. defaults to False
            label (str): the label required by the worker to have a runtime task dispatched to it.
               'local' is equivalent to calling self.mode(local=True).
            task (dict): if specified applied to the task kwargs
            logging (str|tuple): if specified, same as runtime.mode(logging=...)
            override (bool): if True overrides previously set .require(), defaults to True
            kwargs: requirements specification that the runtime understands

        Usage:
            om.runtime.require(label='gpu').model('foo').fit(...)

        Returns:
            self
        """
        if label is not None:
            if label == 'local':
                self.mode(local=True)
            elif override:
                self.mode(local=False)
            # update routing, don't replace (#416)
            routing = routing or {}
            routing.update({'label': label or self._default_label})
        task = task or {}
        routing = routing or {}
        if task or routing:
            if not override:
                # override not allowed, remove previously existing
                ex_task = dict(**self._task_default_kwargs['task'],
                               **self._require_kwargs['task'])
                ex_routing = dict(**self._task_default_kwargs['routing'],
                                  **self._require_kwargs['routing'])
                exists_or_none = lambda k, d: k not in d or d.get(k, False) is None
                task = {k: v for k, v in task.items() if exists_or_none(k, ex_task)}
                routing = {k: v for k, v in routing.items() if exists_or_none(k, ex_routing)}
            if always:
                self._task_default_kwargs['routing'].update(routing)
                self._task_default_kwargs['task'].update(task)
            else:
                self._require_kwargs['routing'].update(routing)
                self._require_kwargs['task'].update(task)
        else:
            # FIXME this does not work as expected (will only reset if both task and routing are False)
            if not task:
                self._require_kwargs['task'] = {}
            if not routing:
                self._require_kwargs['routing'] = {}
        if logging is not None:
            self.mode(logging=logging)
        return self

    def model(self, modelname, require=None):
        """
        return a model for remote execution

        Args:
            modelname (str): the name of the object in om.models
            require (dict): routing requirements for this job

        Returns:
            OmegaModelProxy
        """
        from omegaml.runtimes.proxies.modelproxy import OmegaModelProxy
        self.require(**self._sanitize_require(require)) if require else None
        return OmegaModelProxy(modelname, runtime=self)

    def job(self, jobname, require=None):
        """
        return a job for remote execution

        Args:
            jobname (str): the name of the object in om.jobs
            require (dict): routing requirements for this job

        Returns:
            OmegaJobProxy
        """
        from omegaml.runtimes.proxies.jobproxy import OmegaJobProxy

        self.require(**self._sanitize_require(require)) if require else None
        return OmegaJobProxy(jobname, runtime=self)

    def script(self, scriptname, require=None):
        """
        return a script for remote execution

        Args:
            scriptname (str): the name of object in om.scripts
            require (dict): routing requirements for this job

        Returns:
            OmegaScriptProxy
        """
        from omegaml.runtimes.proxies.scriptproxy import OmegaScriptProxy

        self.require(**self._sanitize_require(require)) if require else None
        return OmegaScriptProxy(scriptname, runtime=self)

    def experiment(self, experiment, provider=None, implied_run=True, recreate=False, **tracker_kwargs):
        """ set the tracking backend and experiment

        Args:
            experiment (str): the name of the experiment
            provider (str): the name of the provider
            tracker_kwargs (dict): additional kwargs for the tracker
            recreate (bool): if True, recreate the experiment (i.e. drop and recreate,
              this is useful to change the provider or other settings. All previous data will
              be kept)

        Returns:
            OmegaTrackingProxy
        """
        from omegaml.runtimes.proxies.trackingproxy import OmegaTrackingProxy
        # tracker implied_run means we are using the currently active run, i.e. with block will call exp.start()
        tracker = OmegaTrackingProxy(experiment, provider=provider, runtime=self, implied_run=implied_run,
                                     recreate=recreate, **tracker_kwargs)
        return tracker

    def task(self, name, **kwargs):
        """
        retrieve the task function from the celery instance

        Args:
            name (str): a registered celery task as ``module.tasks.task_name``
            kwargs (dict): routing keywords to CeleryTask.apply_async

        Returns:
            CeleryTask
        """
        taskfn = self.celeryapp.tasks.get(name)
        assert taskfn is not None, "cannot find task {name} in Celery runtime".format(**locals())
        kwargs = dict_merge(self._common_kwargs, dict(routing=kwargs))
        task = CeleryTask(taskfn, kwargs)
        self._require_kwargs = dict(routing={}, task={})
        return task

    def result(self, task_id, wait=True):
        from celery.result import AsyncResult
        promise = AsyncResult(task_id, app=self.celeryapp)
        return promise.get() if wait else promise

    def settings(self, require=None):
        """ return the runtimes's cluster settings
        """
        self.require(**require) if require else None
        return self.task('omegaml.tasks.omega_settings').delay().get()

    def ping(self, *args, require=None, wait=True, timeout=10, **kwargs):
        """
        ping the runtime

        Args:
            args (tuple): task args
            require (dict): routing requirements for this job
            wait (bool): if True, wait for the task to return, else return
                AsyncResult
            timeout (int): if wait is True, the timeout in seconds, defaults to 10
            kwargs (dict): task kwargs, as accepted by CeleryTask.apply_async

        Returns:
            * response (dict) for wait=True
            * AsyncResult for wait=False
        """
        self.require(**require) if require else None
        promise = self.task('omegaml.tasks.omega_ping').delay(*args, **kwargs)
        return promise.get(timeout=timeout) if wait else promise

    def enable_hostqueues(self):
        """ enable a worker-specific queue on every worker host

        Returns:
            list of labels (one entry for each hostname)
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
        local_worker = {gethostname(): [{'name': 'local', 'is_local': True}]}
        celery_workers = self._inspect.active() or {}
        return dict_merge(local_worker, celery_workers)

    def queues(self):
        """ list queues

        Returns:
            dict of workers => list of queues

        See Also:
            celery Inspect.active_queues()
        """
        local_q = {gethostname(): [{'name': 'local', 'is_local': True}]}
        celery_qs = self._inspect.active_queues() or {}
        return dict_merge(local_q, celery_qs)

    def labels(self):
        """ list available labels

        Returns:
            dict of workers => list of lables
        """
        return {worker: [q.get('name') for q in queues]
                for worker, queues in self.queues().items()}

    def stats(self):
        """ worker statistics

        Returns:
            dict of workers => dict of stats

        See Also:
            celery Inspect.stats()
        """
        return self._inspect.stats()

    def status(self):
        """ current cluster status

        This collects key information from .labels(), .stats() and the latest
        worker heartbeat. Note that loadavg is only available if the worker has
        recently sent a heartbeat and may not be accurate across the cluster.

        Returns:
             snapshot (dict): a snapshot of the cluster status
                '<worker>': {
                    'loadavg': [0.0, 0.0, 0.0],  # load average in % seen by the worker (1, 5, 15 min)
                    'processes': 1, # number of active worker processes
                    'concurrency': 1, # max concurrency
                    'uptime': 0, # uptime in seconds
                    'processed': Counter(task=n), # number of tasks processed
                    'queues': ['default'], # list of queues (labels) the worker is listening on
                }
        """
        labels = self.labels()
        stats = self.stats()
        heartbeat = self.events.latest()
        snapshot = {
            worker: {
                'loadavg': heartbeat.get('loadavg', []),
                'processes': stats[worker]['pool']['processes'],
                'concurrency': stats[worker]['pool']['max-concurrency'],
                'uptime': stats[worker]['uptime'],
                'processed': stats[worker]['total'],
                'queues': labels[worker],
            } for worker in labels if worker in stats
        }
        return snapshot

    @property
    def events(self):
        return CeleryEventStream(self.celeryapp)

    def callback(self, script_name, always=False, **kwargs):
        """ Add a callback to a registered script

        The callback will be triggered upon successful or failed
        execution of the runtime tasks. The script syntax is::

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


class CeleryEventStream:
    def __init__(self, app, limit=None, timeout=5, wakeup=False):
        self.app = app
        self.limit = limit
        self.timeout = timeout
        self.wakeup = wakeup
        self.max_size = 100
        self.buffer = []

    def handle(self, event):
        self.buffer.append(event)
        if len(self.buffer) > self.max_size:
            self.buffer = self.buffer[-1 * self.max_size:]

    def listen(self, handlers=None, limit=None, timeout=None):
        # Connect to the broker using Kombu (Celery's underlying messaging system)
        handlers = handlers or {'worker-heartbeat': self.handle}
        limit = limit or self.limit
        timeout = timeout or self.timeout
        with self.app.connection() as conn:
            # Create the EventReceiver to listen to all events
            recv = EventReceiver(conn, handlers=handlers, app=self.app)
            recv.capture(limit=limit, timeout=timeout, wakeup=self.wakeup)

    def latest(self, timeout=None):
        while len(self.buffer) == 0:
            self.listen(limit=1, timeout=timeout)
        return self.buffer[-1]


# apply mixins
from omegaml.runtimes.mixins.taskcanvas import canvas_chain, canvas_group, canvas_chord
from omegaml.runtimes.mixins.swagger import SwaggerGenerator

OmegaRuntime.sequence = canvas_chain
OmegaRuntime.parallel = canvas_group
OmegaRuntime.mapreduce = canvas_chord
OmegaRuntime.swagger = SwaggerGenerator.build_swagger
