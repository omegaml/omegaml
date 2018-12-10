from __future__ import absolute_import

from celery import Celery

from omegaml.runtimes.jobproxy import OmegaJobProxy
from omegaml.util import settings


class OmegaRuntime(object):
    """
    omegaml compute cluster gateway 
    """

    def __init__(self, omega, backend=None,
                 broker=None, celerykwargs=None, celeryconf=None, auth=None,
                 defaults=None):
        self.backend = backend or 'amqp'
        self.broker = broker or 'amqp://guest@localhost//'
        self.omega = omega
        self._auth = auth
        defaults = defaults or settings()
        # initialize celery as a runtimes
        taskpkgs = defaults.OMEGA_CELERY_IMPORTS
        celerykwargs = celerykwargs or {}
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
        return 'OmegaRuntime({}, auth={})'.format(self.omega.__repr__(), self.auth.__repr__())

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

    def script(self, scriptname):
        """
        return a script for remote execution
        """
        from omegaee.runtime.scriptproxy import OmegaScriptProxy
        return OmegaScriptProxy(scriptname, runtime=self)

    def task(self, name):
        """
        retrieve the task function from the celery instance

        we do it like this so we can per-OmegaRuntime instance
        celery configurations (as opposed to using the default app's
        import, which seems to confuse celery)
        """
        #import omegapkg.tasks
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

    @property
    def auth(self):
        """
        return the current client authentication or None if not configured
        """
        defaults = self.omega.defaults
        if self._auth is None:
            try:
                from omegacommon.auth import OmegaRuntimeAuthentication
                kwargs = dict(userid=getattr(defaults, 'OMEGA_USERID'),
                              apikey=getattr(defaults, 'OMEGA_APIKEY'),
                              qualifier=getattr(defaults, 'OMEGA_QUALIFIER', 'default'))
                self._auth = OmegaRuntimeAuthentication(**kwargs)
            except:
                # we don't set authentication if not provided
                class DummyAuth(object):
                    pass
                self._auth = DummyAuth()
                self._auth.userid = None
                self._auth.apikey = None
                self._auth.qualifier = None
        return self._auth

    @property
    def auth_tuple(self):
        auth = self.auth
        return auth.userid, auth.apikey, auth.qualifier
