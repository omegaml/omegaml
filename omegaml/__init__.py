from __future__ import absolute_import

import logging

from omegaml.util import load_class, settings
import omegaml.defaults as _base_config

logger = logging.getLogger(__file__)

try:
    from omegaee import omega as _omega
except Exception as e:
    from omegaml import omega as _omega
except:
    pass

# link implementation
setup = _omega.setup
version = _omega.version
get_omega_for_task = _omega.get_omega_for_task
Omega = _omega.Omega
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
#: the OmegaSimpleLogger for easy log access
logger = _omega.OmegaDeferredInstance(_omega._om, 'logger')
#: the settings object
defaults = _omega.OmegaDeferredInstance(_omega._om, 'defaults')

