from __future__ import absolute_import

from celery import Celery

from omegaml.runtimes.jobproxy import OmegaJobProxy
from omegaml.util import settings
import logging

logger = logging.getLogger(__name__)


class CeleryTask(object):
    """
    A thin wrapper for a Celery.Task object

    This is so that we can collect common delay arguments on the
    .task() call
    """

    def __init__(self, task, **kwargs):
        """

        Args:
            task (Celery.Task): the celery task object
            **kwargs (dict): optional, the kwargs to pass to apply_async
        """
        self.task = task
        self.kwargs = kwargs

    def apply_async(self, args=None, kwargs=None, *args_, **kwargs_):
        kwargs_.update(self.kwargs)
        return self.task.apply_async(args=args, kwargs=kwargs, *args_)

    def delay(self, *args, **kwargs):
        """
        submit the task with args and kwargs to pass on

        This calls task.apply_async and passes on the self.kwargs.
        """
        return self.apply_async(args=args, kwargs=kwargs, **self.kwargs)

    def run(self, *args, **kwargs):
        return self.delay(*args, **kwargs)


class OmegaRuntime(object):
    """
    omegaml compute cluster gateway 
    """

    def __init__(self, omega, defaults=None, celeryconf=None):
        self.omega = omega
        defaults = defaults or settings()
        self.pure_python = getattr(defaults, 'OMEGA_FORCE_PYTHON_CLIENT', False)
        self.pure_python = self.pure_python or self._client_is_pure_python()
        # initialize celery as a runtimes
        taskpkgs = defaults.OMEGA_CELERY_IMPORTS
        celeryconf = celeryconf or defaults.OMEGA_CELERY_CONFIG
        self.celeryapp = Celery('omegaml')
        self.celeryapp.config_from_object(celeryconf)
        # needed to get it to actually load the tasks (???)
        # https://stackoverflow.com/a/35735471
        self.celeryapp.autodiscover_tasks(taskpkgs, force=True)
        self.celeryapp.finalize()
        # temporary requirements, use .require() to set
        self._require_kwargs = {}
        # fixed default arguments, use .require(always=True) to set
        self._task_default_kwargs = {}

    def __repr__(self):
        return 'OmegaRuntime({})'.format(self.omega.__repr__())

    @property
    def _common_kwargs(self):
        common = dict(pure_python=self.pure_python)
        common.update(self._task_default_kwargs)
        common.update(self._require_kwargs)
        return common

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

    def require(self, always=False, **kwargs):
        """
        specify requirements for the task execution

        Use this to specify resource or routing requirements on the next task
        call sent to the runtime. Any requirements will be reset after the
        call has been submitted.

        Args:
            always (bool): if True requirements will persist across task calls. defaults to False
            **kwargs: requirements specification that the runtime understands

        Usage:
            # celery runtime
            om.runtime.require(queue='gpu').model('foo').fit(...)

            # dask distributed runtime
            om.runtime.require(resource='gpu').model('foo').fit(...)

        Returns:
            self
        """
        if always:
            self._task_default_kwargs.update(kwargs)
        else:
            self._require_kwargs.update(kwargs)
        return self

    def model(self, modelname, require=None):
        """
        return a model for remote execution
        """
        from omegaml.runtimes.modelproxy import OmegaModelProxy
        self.require(require) if require else None
        return OmegaModelProxy(modelname, runtime=self)

    def job(self, jobname, require=None):
        """
        return a job for remote exeuction
        """
        self.require(require) if require else None
        return OmegaJobProxy(jobname, runtime=self)

    def task(self, name, **kwargs):
        """
        retrieve the task function from the celery instance

        we do it like this so we can per-OmegaRuntime instance
        celery configurations (as opposed to using the default app's
        import, which seems to confuse celery)
        """
        # import omegapkg.tasks
        kwargs.update(self._common_kwargs)
        taskfn = self.celeryapp.tasks.get(name)
        assert taskfn is not None, "cannot find task {name} in Celery runtime"
        task = CeleryTask(taskfn, **kwargs)
        self._require_kwargs = {}
        return task

    def settings(self, require=None):
        """
        return the runtimes's cluster settings
        """
        self.require(require) if require else None
        return self.task('omegaml.tasks.omega_settings').delay().get()

    def ping(self, require=None, *args, **kwargs):
        """
        ping the runtimes
        """
        self.require(require) if require else None
        return self.task('omegaml.tasks.omega_ping').delay(*args, **kwargs).get()
