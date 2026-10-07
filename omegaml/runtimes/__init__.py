from omegaml.runtimes.proxies.jobproxy import OmegaJobProxy as OmegaJobProxy
from omegaml.runtimes.proxies.modelproxy import OmegaModelProxy as OmegaModelProxy

from .daskruntime import OmegaRuntimeDask as OmegaRuntimeDask
from .loky import OmegaRuntimeBackend as OmegaRuntimeBackend
from .runtime import OmegaRuntime as OmegaRuntime
