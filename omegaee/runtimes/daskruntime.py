from __future__ import absolute_import

from omegaml import load_class
from omegaml.client.auth import AuthenticationEnv
from omegaml.runtimes import OmegaRuntimeDask
from omegaml.runtimes.scriptproxy import OmegaScriptProxy


class OmegaAuthenticatedRuntimeDask(OmegaRuntimeDask):
    """
    omegaml compute cluster gateway to a dask distributed cluster

    set environ DASK_DEBUG=1 to run dask tasks locally
    """

    def __init__(self, omega, auth=None, **kwargs):
        super().__init__(omega, **kwargs)
        self._auth = auth

    @property
    def _common_kwargs(self):
        return dict(__auth=self.runtime.auth.token,
                    pure_python=self.pure_python)

    def script(self, scriptname):
        """
        return a script for remote execution
        """
        return OmegaScriptProxy(scriptname, runtime=self)

    @property
    def auth(self):
        """
        return the current client authentication or None if not configured
        """
        if self._auth is None:
            auth_env = AuthenticationEnv.secure()
            self._auth = auth_env.get_runtime_auth(om=self.omega)
        return self._auth
