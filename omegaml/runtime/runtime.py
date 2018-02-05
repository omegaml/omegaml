from __future__ import absolute_import

from celery import Celery

from omegacommon.auth import OmegaRuntimeAuthentication
from omegaml import defaults
from omegaml.util import settings


class OmegaRuntime(object):

    """
    omegaml compute cluster gateway 
    """

    def __init__(self, omega, backend=None,
                 broker=None, celerykwargs=None, celeryconf=None, auth=None):
        self.backend = backend or 'amqp'
        self.broker = broker or 'amqp://guest@localhost//'
        self.omega = omega
        self._auth = auth
        # initialize celery as a runtime
        # needed to get it to actually load the tasks (???)
        from omegaml import tasks 
        from omegajobs import tasks
        celerykwargs = celerykwargs or {}
        celerykwargs.update({'backend': self.backend,
                             'broker': self.broker,
                             'include': ['omega.tasks', 'omegajobs.tasks']
                             })
        defaults = settings()
        celeryconf = celeryconf or defaults.OMEGA_CELERY_CONFIG
        self.celeryapp = Celery('omegaml', **celerykwargs)
        self.celeryapp.conf.update(celeryconf)
        self.celeryapp.finalize()

    def deploy(self, modelname):
        # dokku deploy to container
        pass

    def model(self, modelname):
        """
        return a model for remote execution
        """
        from omegaml.runtime.modelproxy import OmegaModelProxy
        return OmegaModelProxy(modelname, runtime=self)

    def job(self, jobname):
        """
        return a job for remote exeuction
        """
        from omegaml.runtime.jobproxy import OmegaJobProxy
        return OmegaJobProxy(jobname, runtime=self)

    def task(self, name):
        """
        retrieve the task function from the celery instance

        we do it like this so we can per-OmegaRuntime instance
        celery configurations (as opposed to using the default app's
        import, which seems to confuse celery)
        """
        return self.celeryapp.tasks.get(name)

    def settings(self):
        """
        return the runtime's cluster settings
        """
        return self.task('omegaml.tasks.omega_settings').delay().get()

    @property
    def auth(self):
        """
        return the current client authentication or None if not configured
        """
        if self._auth is None:
            try:
                kwargs = dict(userid=getattr(defaults, 'OMEGA_USERID'),
                              apikey=getattr(defaults, 'OMEGA_APIKEY'))
                self._auth = OmegaRuntimeAuthentication(**kwargs)
            except:
                # we don't set authentication if not provided
                pass
        return self._auth

    @property
    def auth_tuple(self):
        auth = self.auth
        return auth.userid, auth.apikey
