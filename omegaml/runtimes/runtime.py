from __future__ import absolute_import

from celery import Celery

from omegaml.runtimes.jobproxy import OmegaJobProxy
from omegaml.util import settings


class OmegaRuntime(object):
    """
    omegaml compute cluster gateway 
    """

    def __init__(self, omega, backend=None,
                 broker=None, celerykwargs=None, celeryconf=None, defaults=None):
        self.backend = backend or 'amqp'
        self.broker = broker or 'amqp://guest@localhost//'
        self.omega = omega
        defaults = defaults or settings()
        # initialize celery as a runtimes
        taskpkgs = defaults.OMEGA_CELERY_IMPORTS
        celerykwargs = celerykwargs or defaults.OMEGA_CELERY_CONFIG
        celerykwargs.update({'backend': self.backend,
                             'broker': self.broker,
                             'include': taskpkgs,
                             })
        celeryconf = celeryconf or defaults.OMEGA_CELERY_CONFIG
        self.celeryapp = Celery('omegaml', **celerykwargs)
        self.celeryapp.conf.update(celeryconf)
        # needed to get it to actually load the tasks (???)
        # https://stackoverflow.com/a/35735471
        self.celeryapp.autodiscover_tasks(taskpkgs, force=True)
        self.celeryapp.finalize()

    def __repr__(self):
        return 'OmegaRuntime({})'.format(self.omega.__repr__())

    def model(self, modelname):
        """
        return a model for remote execution
        """
        from omegaml.runtimes.modelproxy import OmegaModelProxy
        return OmegaModelProxy(modelname, runtime=self)

    def job(self, jobname):
        """
        return a job for remote exeuction
        """
        return OmegaJobProxy(jobname, runtime=self)

    def task(self, name):
        """
        retrieve the task function from the celery instance

        we do it like this so we can per-OmegaRuntime instance
        celery configurations (as opposed to using the default app's
        import, which seems to confuse celery)
        """
        # import omegapkg.tasks
        return self.celeryapp.tasks.get(name)

    def settings(self):
        """
        return the runtimes's cluster settings
        """
        return self.task('omegaml.tasks.omega_settings').delay().get()

    def ping(self, *args, **kwargs):
        """
        ping the runtimes
        """
        return self.task('omegaml.tasks.omega_ping').delay(*args, **kwargs).get()
