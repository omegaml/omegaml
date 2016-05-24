import logging
from uuid import uuid4

from celery import Celery
from omegaml.documents import Metadata
from omegaml.store import OmegaStore
from omegaml.jobs import OmegaJobs
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

    Implementation note:

        We decided to implement each method call explicitely in both
        this class and the celery tasks. While it would be possible to
        implement a generic method and task that passes the method and
        arguments to be called, maintainability would suffer and the
        documentation would become very unspecific. We think it is much
        cleaner to have an explicit interface at the chance of missing
        features. If need should arise we can still implement a generic
        method call.
    """

    def __init__(self, modelname, runtime=None):
        self.modelname = modelname
        self.runtime = runtime
        self.pure_python = getattr(settings(), 'OMEGA_FORCE_PYTHON_CLIENT',
                                   False)
        self.pure_python = self.pure_python or self._client_is_pure_python()

    def fit(self, Xname, Yname=None, **kwargs):
        """
        fit the model

        Calls .fit(X, Y, **kwargs). If instead of dataset names actual data
        is given, the data is stored using _fitX/fitY prefixes and a unique
        name.

        After fitting, a new model version is stored with its attributes
        fitX and fitY pointing to the datasets, as well as the sklearn
        version used.

        :param Xname: name of X dataset or data
        :param Yname: name of Y dataset or data
        :return: the model (self) or the string representation (python clients)
        """
        omega_fit = self.runtime.task('omegaml.tasks.omega_fit')
        Xname = self._ensure_data_is_stored(Xname, prefix='_fitX')
        if Yname is not None:
            Yname = self._ensure_data_is_stored(Yname, prefix='_fitY')
        return omega_fit.delay(self.modelname, Xname, Yname,
                               pure_python=self.pure_python, **kwargs)

    def partial_fit(self, Xname, Yname=None, **kwargs):
        """
        update the model

        Calls .partial_fit(X, Y, **kwargs). If instead of dataset names actual
        data  is given, the data is stored using _fitX/fitY prefixes and
        a unique name.

        After fitting, a new model version is stored with its attributes
        fitX and fitY pointing to the datasets, as well as the sklearn
        version used.

        :param Xname: name of X dataset or data
        :param Yname: name of Y dataset or data
        :return: the model (self) or the string representation (python clients)
        """
        omega_fit = self.runtime.task('omegaml.tasks.omega_partial_fit')
        Xname = self._ensure_data_is_stored(Xname, prefix='_fitX')
        if Yname is not None:
            Yname = self._ensure_data_is_stored(Yname, prefix='_fitY')
        return omega_fit.delay(self.modelname, Xname, Yname,
                               pure_python=self.pure_python, **kwargs)

    def transform(self, Xname, rName=None, **kwargs):
        """
        transform X

        Calls .transform(X, **kwargs). If rName is given the result is
        stored as object rName

        :param Xname: name of the X dataset
        :param rName: name of the resulting dataset (optional)
        :return: the data returned by .transform, or the metadata of the rName
        dataset if rName was given
        """
        omega_transform = self.runtime.task('omegaml.tasks.omega_transform')
        Xname = self._ensure_data_is_stored(Xname)
        return omega_transform.delay(self.modelname, Xname,
                                     rName=rName,
                                     pure_python=self.pure_python, **kwargs)

    def fit_transform(self, Xname, Yname=None, rName=None, **kwargs):
        """
        fit & transform X

        Calls .fit_transform(X, Y, **kwargs). If rName is given the result is
        stored as object rName

        :param Xname: name of the X dataset
        :param Yname: name of the Y dataset
        :param rName: name of the resulting dataset (optional)
        :return: the data returned by .fit_transform, or the metadata of the rName
        dataset if rName was given
        """

        omega_fit_transform = self.runtime.task(
            'omegaml.tasks.omega_fit_transform')
        Xname = self._ensure_data_is_stored(Xname)
        if Yname is not None:
            Yname = self._ensure_data_is_stored(Yname)
        return omega_fit_transform.delay(self.modelname, Xname, Yname,
                                         rName=rName, transform=True,
                                         pure_python=self.pure_python, **kwargs)

    def predict(self, Xpath_or_data, rName=None, **kwargs):
        """
        predict

        Calls .predict(X). If rName is given the result is
        stored as object rName

        :param Xname: name of the X dataset
        :param rName: name of the resulting dataset (optional)
        :return: the data returned by .predict, or the metadata of the rName
        dataset if rName was given
        """
        omega_predict = self.runtime.task('omegaml.tasks.omega_predict')
        Xname = self._ensure_data_is_stored(Xpath_or_data)
        return omega_predict.delay(self.modelname, Xname, rName=rName,
                                   pure_python=self.pure_python, **kwargs)

    def predict_proba(self, Xpath_or_data, rName=None, **kwargs):
        """
        predict probabilities

        Calls .predict_proba(X). If rName is given the result is
        stored as object rName

        :param Xname: name of the X dataset
        :param rName: name of the resulting dataset (optional)
        :return: the data returned by .predict_proba, or the metadata of the rName
        dataset if rName was given
        """
        omega_predict_proba = self.runtime.task(
            'omegaml.tasks.omega_predict_proba')
        Xname = self._ensure_data_is_stored(Xpath_or_data)
        return omega_predict_proba.delay(self.modelname, Xname, rName=rName,
                                         pure_python=self.pure_python, **kwargs)

    def score(self, Xname, yName, rName=None, **kwargs):
        """
        calculate score

        Calls .score(X, y, **kwargs). If rName is given the result is
        stored as object rName

        :param Xname: name of the X dataset
        :param yName: name of the y dataset
        :param rName: name of the resulting dataset (optional)
        :return: the data returned by .score, or the metadata of the rName
        dataset if rName was given
        """
        omega_score = self.runtime.task('omegaml.tasks.omega_score')
        Xname = self._ensure_data_is_stored(Xname)
        yName = self._ensure_data_is_stored(yName)
        return omega_score.delay(self.modelname, Xname, rName=rName,
                                 pure_python=self.pure_python, **kwargs)

    def _ensure_data_is_stored(self, name_or_data, prefix='_temp'):
        if is_dataframe(name_or_data):
            name = '%s_%s' % (prefix, uuid4().hex)
            self.runtime.omega.datasets.put(name_or_data, name)
        elif is_ndarray(name_or_data):
            name = '%s_%s' % (prefix, uuid4().hex)
            self.runtime.omega.datasets.put(name_or_data, name)
        elif isinstance(name_or_data, (list, tuple, dict)):
            name = '%s_%s' % (prefix, uuid4().hex)
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

    def settings(self):
        return self.task('omegaml.tasks.omega_settings').delay().get()


class Omega(object):

    def __init__(self, backend=None, broker=None,
                 celeryconf=None, celerykwargs=None):
        defaults = settings()
        self.broker = broker or defaults.OMEGA_BROKER
        self.backend = backend or defaults.OMEGA_RESULT_BACKEND
        self.models = OmegaStore(
            prefix='models/',
            kind=Metadata.SKLEARN_JOBLIB)
        self.datasets = OmegaStore(prefix='data/')
        self.runtime = OmegaRuntime(self, backend=backend,
                                    broker=broker, celeryconf=celeryconf,
                                    celerykwargs=None)
        self.jobs = OmegaJobs()


# default instance
_om = Omega()
models = _om.models
datasets = _om.datasets
runtime = _om.runtime
