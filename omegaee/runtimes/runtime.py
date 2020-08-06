from __future__ import absolute_import

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
            from omegaml.client.auth import OmegaRuntimeAuthentication
            kwargs = dict(userid=getattr(defaults, 'OMEGA_USERID'),
                          apikey=getattr(defaults, 'OMEGA_APIKEY'),
                          qualifier=getattr(defaults, 'OMEGA_QUALIFIER', 'default'))
            self._auth = OmegaRuntimeAuthentication(**kwargs)
        return self._auth

    @property
    def auth_tuple(self):
        auth = self.auth
        return auth.userid, auth.apikey, auth.qualifier

    def __repr__(self):
        return 'OmegaAuthenticatedRuntime({}, auth={})'.format(self.omega.__repr__(), self.auth.__repr__())


