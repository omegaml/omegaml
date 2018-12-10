from __future__ import absolute_import

import logging

from omegaml.jobs import OmegaJobs
from omegaml.runtimes import OmegaRuntime
from omegaml.store import OmegaStore
from omegaml.util import load_class, settings
from ._version import version

logger = logging.getLogger(__file__)

try:
    from omegaee.omega import OmegaDeferredInstance, setup, _om
except:
    from omegaml.omega import OmegaDeferredInstance, setup, _om

datasets = OmegaDeferredInstance(_om, 'datasets')
#: the OmegaStore for models
models = OmegaDeferredInstance(_om, 'models')
#: the jobs API
jobs = OmegaDeferredInstance(_om, 'jobs')
#: the OmegaStore for lambda scripts
scripts = OmegaDeferredInstance(_om, 'scripts')
#: the OmegaRuntime for cluster execution
runtime = OmegaDeferredInstance(_om, 'runtimes')
