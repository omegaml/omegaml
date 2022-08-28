import cachetools

from omegaml import defaults as _base_config
from omegaml._version import version
from omegaml.omega import OmegaDeferredInstance
from omegaml.util import load_class, settings, base_loader

# session cache must be defined here globally so can be imported from anywhere
# without causing circular import issues
#: session cache
session_cache = cachetools.cached(cache=cachetools.TTLCache(**_base_config.OMEGA_SESSION_CACHE))

# link implementation
def link(_omega):
    # link a specific implementation lazy loaded at runtime
    global datasets, models, jobs, scripts, runtime, streams, logger, defaults, setup, version
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


# load base and lazy link
# -- base_loader only loads classes, does not instantiate
# -- deferred instance provides setup to load and link on access
_omega = base_loader(_base_config)
setup = _omega.setup
version = getattr(_omega, 'version', version)
Omega = _omega.Omega
_omega.OmegaDeferredInstance = getattr(_omega, 'OmegaDeferredInstance', OmegaDeferredInstance)
# setup API
#: the :class:`omegaml.store.base.OmegaStore` store for datasets
datasets = _omega.OmegaDeferredInstance(_omega._om, 'datasets')
#: the :class:`omegaml.store.base.OmegaStore` store for models
models = _omega.OmegaDeferredInstance(_omega._om, 'models')
#: the :class:`omegaml.notebook.jobs.OmegaJobs` store for jobs
jobs = _omega.OmegaDeferredInstance(_omega._om, 'jobs')
#: the :class:`omegaml.store.base.OmegaStore` store for scripts
scripts = _omega.OmegaDeferredInstance(_omega._om, 'scripts')
#: the :class:`omegaml.runtimes.runtime.OmegaRuntime` runtime
runtime = _omega.OmegaDeferredInstance(_omega._om, 'runtime')
#: stream helper
streams = _omega.OmegaDeferredInstance(_omega._om, 'streams')
#: the OmegaSimpleLogger for easy log access
logger = _omega.OmegaDeferredInstance(_omega._om, 'logger')
#: the settings object
defaults = _omega.OmegaDeferredInstance(_omega._om, 'defaults')
