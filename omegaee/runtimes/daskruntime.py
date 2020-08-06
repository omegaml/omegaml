from __future__ import absolute_import

from omegaml.client.auth import OmegaRuntimeAuthentication
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
        return dict(__auth=self.runtime.auth_tuple, pure_python=self.pure_python)

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
        defaults = self.omega.defaults
        if self._auth is None:
            kwargs = dict(userid=getattr(defaults, 'OMEGA_USERID'),
                          apikey=getattr(defaults, 'OMEGA_APIKEY'),
                          qualifier=getattr(defaults, 'OMEGA_QUALIFIER', 'default'))
            self._auth = OmegaRuntimeAuthentication(**kwargs)
        return self._auth

    @property
    def auth_tuple(self):
        auth = self.auth
        return auth.userid, auth.apikey, auth.qualifier
