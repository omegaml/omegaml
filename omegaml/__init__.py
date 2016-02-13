import logging
from uuid import uuid4

from celery import Celery

from omegaml.store import OmegaStore
from omegaml.util import is_dataframe, settings, is_ndarray
logger = logging.getLogger(__file__)


class OmegaModelProxy(object):

    """
    proxy to a remote model in a celery worker

    The proxy provides the same methods as the model but will
    execute the methods using celery tasks and return celery
    AsyncResult objects

    Usage:

        om = Omega()
        # train a model
        # result is AsyncResult, use .get() to return it's result
        result = om.runtime.model('foo').fit('datax', 'datay')
        result.get()

        # predict
        result = om.runtime.model('foo').predict('datax')
        # result is AsyncResult, use .get() to return it's result
        print result.get()
    """

    def __init__(self, modelname, runtime=None):
        self.modelname = modelname
        self.runtime = runtime
        self.pure_python = getattr(settings(), 'OMEGA_FORCE_PYTHON_CLIENT',
                                   False)
        self.pure_python = self.pure_python or self._client_is_pure_python()

    def fit(self, Xname, Yname):
        omega_fit = self.runtime.task('omegaml.tasks.omega_fit')
        Xname = self._ensure_data_is_stored(Xname)
        Yname = self._ensure_data_is_stored(Yname)
        return omega_fit.delay(self.modelname, Xname, Yname,
                               pure_python=self.pure_python)

    def predict(self, Xpath_or_data):
        omega_predict = self.runtime.task('omegaml.tasks.omega_predict')
        Xname = self._ensure_data_is_stored(Xpath_or_data)
        return omega_predict.delay(self.modelname, Xname,
                                   pure_python=self.pure_python)

    def _ensure_data_is_stored(self, name_or_data):
        if is_dataframe(name_or_data):
            name = '_temp_%s' % uuid4().hex
            self.runtime.omega.datasets.put(name_or_data, name)
        elif is_ndarray(name_or_data):
            name = '_temp_%s' % uuid4().hex
            self.runtime.omega.datasets.put(name_or_data, name)
        elif isinstance(name_or_data, (list, tuple, dict)):
            name = '_temp_%s' % uuid4().hex
            self.runtime.omega.datasets.put(name_or_data, name)
        elif isinstance(name_or_data, basestring):
            name = name_or_data
        else:
            raise TypeError(
                'invalid type for Xpath_or_data', type(name_or_data))
        return name

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


class OmegaRuntime(object):

    def __init__(self, omega, backend=None,
                 broker=None, celerykwargs=None, celeryconf=None):
        self.backend = backend or 'amqp://'
        self.broker = broker or 'amqp://guest@localhost//'
        self.omega = omega
        # initialize celery as a runtime
        celerykwargs = celerykwargs or {}
        celerykwargs.update({'backend': self.backend,
                             'broker': self.broker,
                             'include': ['omega.tasks']
                             })
        defaults = settings()
        celeryconf = celeryconf or defaults.OMEGA_CELERY_CONFIG
        self.celeryapp = Celery('omegaml', **celerykwargs)
        self.celeryapp.conf.update(celeryconf)
        # needed to get it to actually load the tasks (???)
        from omegaml.tasks import omega_fit, omega_predict
        self.celeryapp.finalize()

    def deploy(self, modelname):
        # dokku deploy to container
        pass

    def model(self, modelname):
        """
        return a model for remote execution
        """
        return OmegaModelProxy(modelname, runtime=self)

    def task(self, name):
        """
        retrieve the task function from the celery instance

        we do it like this so we can per-OmegaRuntime instance
        celery configurations (as opposed to using the default app's
        import, which seems to confuse celery)
        """
        return self.celeryapp.tasks.get(name)


class Omega(object):

    def __init__(self, backend=None, broker=None,
                 celeryconf=None, celerykwargs=None):
        defaults = settings()
        backend = backend or defaults.OMEGA_RESULTS_BACKEND
        broker = backend or defaults.OMEGA_BROKER
        self.models = OmegaStore(prefix='models/')
        self.datasets = OmegaStore(prefix='data/')
        self.runtime = OmegaRuntime(self, backend=backend,
                                    broker=broker, celeryconf=celeryconf,
                                    celerykwargs=None)
