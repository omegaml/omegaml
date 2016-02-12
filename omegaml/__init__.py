from celery import Celery

from omega import defaults
import pandas as pd
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

    def fit(self, Xname, Yname):
        omega_fit = self.runtime.task('omega.tasks.omega_fit')
        return omega_fit.delay(self.modelname, Xname, Yname)

    def predict(self, Xpath_or_data):
        omega_predict = self.runtime.task('omega.tasks.omega_predict')
        if isinstance(Xpath_or_data, pd.DataFrame):
            Xname = '_temp'
            self.runtime.omega.datasets.put(Xpath_or_data, Xname)
        else:
            Xname = Xpath_or_data
        return omega_predict.delay(self.modelname, Xname)


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
        celeryconf = celeryconf or defaults.OMEGA_CELERY_CONFIG
        self.celeryapp = Celery('omega', **celerykwargs)
        self.celeryapp.conf.update(celeryconf)
        # needed to get it to actually load the tasks (???)
        from omega.tasks import omega_fit, omega_predict
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
        """
        return self.celeryapp.tasks.get(name)


class Omega(object):

    def __init__(self, backend=None, broker=None,
                 celeryconf=None, celerykwargs=None):
        backend = backend or defaults.OMEGA_RESULTS_BACKEND
        broker = backend or defaults.OMEGA_BROKER
        from store import OmegaStore
        self.models = OmegaStore(prefix='models/')
        self.datasets = OmegaStore(prefix='data')
        self.runtime = OmegaRuntime(self, backend=backend,
                                    broker=broker, celeryconf=celeryconf,
                                    celerykwargs=None)
