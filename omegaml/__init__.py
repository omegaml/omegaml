from __future__ import absolute_import

import logging
from uuid import uuid4

from celery import Celery
import six

from omegaml.documents import Metadata
from omegaml.jobs import OmegaJobs
from omegaml.runtime.proxy import OmegaRuntime
from omegaml.store import OmegaStore
from omegaml.util import is_dataframe, settings, is_ndarray
logger = logging.getLogger(__file__)


class Omega(object):

    def __init__(self, mongo_url=None, backend=None, broker=None,
                 celeryconf=None, celerykwargs=None):
        self.defaults = settings()
        self.broker = broker or self.defaults.OMEGA_BROKER
        self.backend = backend or self.defaults.OMEGA_RESULT_BACKEND
        self.models = OmegaStore(mongo_url=mongo_url, prefix='models/')
        self.datasets = OmegaStore(mongo_url=mongo_url, prefix='data/')
        self.jobdata = OmegaStore(mongo_url=mongo_url, prefix='jobdata/')
        self.runtime = OmegaRuntime(self, backend=backend,
                                    mongo_url=mongo_url,
                                    broker=broker, celeryconf=celeryconf,
                                    celerykwargs=None)
        self.jobs = OmegaJobs(store=self.jobdata)

    def get_data(self, name):
        data = self.datasets.get(name)
        meta = self.datasets.metadata(name)
        if meta.kind == Metadata.PYTHON_DATA:
            # we can only use one python object at a time
            return data[0], meta
        return data, meta


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
