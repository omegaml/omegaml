from __future__ import absolute_import

import logging
from uuid import uuid4

from celery import Celery
import six

from omegaml.documents import Metadata
from omegaml.jobs import OmegaJobs
from omegaml.store import OmegaStore
from omegaml.runtime import OmegaRuntime
from omegaml.util import is_dataframe, settings, is_ndarray
logger = logging.getLogger(__file__)


class Omega(object):

    """
    Client API to omegaml

    Provides the following APIs:

    * :code:`datasets` - access to datasets stored in the cluster
    * :code:`models` - access to models stored in the cluster
    * :code:`runtime` - access to the cluster compute resources
    * :code:`jobs` - access to jobs stored and executed in the cluster

    """

    def __init__(self, mongo_url=None, backend=None, broker=None,
                 celeryconf=None, celerykwargs=None, auth=None):
        """
        Initialize the client API

        Without arguments create the client API according to the user's
        configuration in :code:`~/omegaml/config.yml`. 

        Arguments override the user's configuration.

        :param mongo_url: the fully qualified URI to the mongo database,
        of format :code:`mongodb://user:password@host:port/database`
        :param broker: the celery broker URI
        :param backend: the celery result backend URI
        :param celeryconf: the celery configuration dictionary
        :param celerykwargs: kwargs to create the Celery instance
        """
        self.defaults = settings()
        self.broker = broker or self.defaults.OMEGA_BROKER
        self.backend = backend or self.defaults.OMEGA_RESULT_BACKEND
        self.models = OmegaStore(mongo_url=mongo_url, prefix='models/')
        self.datasets = OmegaStore(mongo_url=mongo_url, prefix='data/')
        self._jobdata = OmegaStore(mongo_url=mongo_url, prefix='jobs/')
        self.runtime = OmegaRuntime(self, backend=backend,
                                    auth=auth,
                                    broker=broker, celeryconf=celeryconf,
                                    celerykwargs=None)
        self.jobs = OmegaJobs(store=self._jobdata)


class OmegaDeferredInstance():

    """
    A deferred instance of Omega() that is only instantiated on access

    This is to ensure that module-level imports don't trigger instantiation
    of Omega. 
    """

    def __init__(self, base=None, attribute=None):
        self.omega = None
        self.base = base
        self.attribute = attribute

    def __getattr__(self, name):
        if self.base:
            base = getattr(self.base, self.attribute)
            return getattr(base, name)
        if self.omega is None:
            self.omega = Omega()
        return getattr(self.omega, name)

# default instance
# -- these are deferred instanced that is the actual Omega instance
#    is only created on actual attribute access
_om = OmegaDeferredInstance()
#: the OmegaStore for data
datasets = OmegaDeferredInstance(_om, 'datasets')
#: the OmegaStore for models
models = OmegaDeferredInstance(_om, 'models')
#: the jobs API
jobs = OmegaDeferredInstance(_om, 'jobs')
#: the OmegaRuntime for cluster execution
runtime = OmegaDeferredInstance(_om, 'runtime')
