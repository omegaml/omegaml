from __future__ import absolute_import

from omegaml import load_class
from omegaml.client.cloud import OmegaCloudRuntime


class OmegaAuthenticatedRuntime(OmegaCloudRuntime):
    def __init__(self, omega, auth=None, **kwargs):
        super().__init__(omega, **kwargs)
        self._auth = auth

    @property
    def auth(self):
        """
        return the current client authentication or default auth if not configured
        """
        defaults = self.omega.defaults
        if self._auth is None:
            auth_env = load_class(defaults.OMEGA_AUTH_ENV)
            RuntimeAuthentication = auth_env.get_runtime_auth(defaults=defaults)
            kwargs = dict(userid=getattr(defaults, 'OMEGA_USERID'),
                          apikey=getattr(defaults, 'OMEGA_APIKEY'),
                          qualifier=getattr(defaults, 'OMEGA_QUALIFIER', 'default'))
            self._auth = RuntimeAuthentication(**kwargs)
        return self._auth

    def __repr__(self):
        return 'OmegaAuthenticatedRuntime({}, auth={})'.format(self.omega.__repr__(), self.auth.__repr__())


