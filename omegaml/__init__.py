from __future__ import absolute_import

import logging

from omegacommon.userconf import get_omega_from_apikey
from omegaml.jobs import OmegaJobs
from omegaml.runtime import OmegaRuntime
from omegaml.store import OmegaStore
from omegaml.util import load_class, settings

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
                 celeryconf=None, celerykwargs=None, auth=None, defaults=None):
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
        from omegaml.documents import Metadata
        from omegaml.util import settings

        self.defaults = defaults or settings()
        self.mongo_url = mongo_url or self.defaults.OMEGA_MONGO_URL
        self.broker = broker or self.defaults.OMEGA_BROKER
        self.backend = backend or self.defaults.OMEGA_RESULT_BACKEND
        self.models = OmegaStore(mongo_url=mongo_url, prefix='models/', defaults=self.defaults)
        self.datasets = OmegaStore(mongo_url=mongo_url, prefix='data/', defaults=self.defaults)
        self._jobdata = OmegaStore(mongo_url=mongo_url, prefix='jobs/', defaults=self.defaults)
        self.runtime = OmegaRuntime(self, backend=backend,
                                    auth=auth,
                                    broker=broker, celeryconf=celeryconf,
                                    celerykwargs=None, defaults=self.defaults)
        self.jobs = OmegaJobs(store=self._jobdata)

    def __repr__(self):
        return 'Omega(mongo_url={})'.format(self.mongo_url)


class OmegaDeferredInstance():
    """
    A deferred instance of Omega() that is only instantiated on access

    This is to ensure that module-level imports don't trigger instantiation
    of Omega.
    """

    def __init__(self, base=None, attribute=None):
        self.omega = 'not initialized -- call .setup() or access an attribute'
        self.initialized = False
        self.base = base
        self.attribute = attribute

    def setup(self, username=None, apikey=None, api_url=None):
        settings()
        if not self.initialized and username and apikey:
            self.omega = get_omega_from_apikey(username, apikey, api_url=api_url)
            self.initialized = True
        else:
            self.omega = Omega()
        return self

    def __getattr__(self, name):
        if self.base:
            base = getattr(self.base, self.attribute)
            return getattr(base, name)
        self.setup()
        return getattr(self.omega, name)

def __repr__():
    return getattr(_om, 'omega').__repr__()

def repr():
    return __repr__()

def setup(username=None, apikey=None, api_url=None):
    return _om.setup(username=username, apikey=apikey, api_url=api_url).omega

# default instance
# -- these are deferred instanced that is the actual Omega instance
#    is only created on actual attribute access
_om = OmegaDeferredInstance()

datasets = OmegaDeferredInstance(_om, 'datasets')
#: the OmegaStore for models
models = OmegaDeferredInstance(_om, 'models')
#: the jobs API
jobs = OmegaDeferredInstance(_om, 'jobs')
#: the OmegaRuntime for cluster execution
runtime = OmegaDeferredInstance(_om, 'runtime')

