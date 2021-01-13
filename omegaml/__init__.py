import logging

from omegaml import defaults as _base_config

from omegaml._version import version
from omegaml.omega import OmegaDeferredInstance
from omegaml.util import load_class, settings, base_loader

logger = logging.getLogger(__file__)

# link implementation
def link(_omega):
    # link a specific implementation lazy loaded at runtime
    global datasets, models, jobs, scripts, runtime, streams, logger, defaults, setup, version, get_omega_for_task
    datasets = _omega.datasets
    models = _omega.models
    jobs = _omega.jobs
    scripts = _omega.scripts
    runtime = _omega.runtime
    streams = _omega.streams
    logger = _omega.logger
    defaults = _omega.defaults
    setup = getattr(_omega, 'setup', setup)
    version = getattr(_omega, 'version', version)
    get_omega_for_task = getattr(_omega, 'get_omega_for_task', get_omega_for_task)


# load base and lazy link
# -- base_loader only loads classes, does not instantiate
# -- deferred instance provides setup to load and link on access
_omega = base_loader(_base_config)
setup = _omega.setup
version = getattr(_omega, 'version', version)
get_omega_for_task = _omega.get_omega_for_task
Omega = _omega.Omega
_omega.OmegaDeferredInstance = getattr(_omega, 'OmegaDeferredInstance', OmegaDeferredInstance)
# setup API
#: the OmegaStore for datasets
datasets = _omega.OmegaDeferredInstance(_omega._om, 'datasets')
#: the OmegaStore for models
models = _omega.OmegaDeferredInstance(_omega._om, 'models')
#: the jobs API
jobs = _omega.OmegaDeferredInstance(_omega._om, 'jobs')
#: the OmegaStore for lambda scripts
scripts = _omega.OmegaDeferredInstance(_omega._om, 'scripts')
#: the OmegaRuntime for cluster execution
runtime = _omega.OmegaDeferredInstance(_omega._om, 'runtime')
#: stream helper
streams = _omega.OmegaDeferredInstance(_omega._om, 'streams')
#: the OmegaSimpleLogger for easy log access
logger = _omega.OmegaDeferredInstance(_omega._om, 'logger')
#: the settings object
defaults = _omega.OmegaDeferredInstance(_omega._om, 'defaults')
