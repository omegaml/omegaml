from __future__ import absolute_import

from omegaml.runtimes.scriptproxy import OmegaScriptProxy
from omegaml.runtimes import OmegaRuntime, OmegaJobProxy


class OmegaAuthenticatedRuntime(OmegaRuntime):
    """
    omegaml compute cluster gateway 
    """

    def __init__(self, omega, auth=None, **kwargs):
        super().__init__(omega, **kwargs)
        self._auth = auth

    def __repr__(self):
        return 'OmegaRuntime({}, auth={})'.format(self.omega.__repr__(), self.auth.__repr__())

    @property
    def _common_kwargs(self):
        kwargs = super()._common_kwargs
        kwargs['task'].update(__auth=self.auth_tuple)
        return kwargs

    @property
    def auth(self):
        """
        return the current client authentication or None if not configured
        """
        defaults = self.omega.defaults
        if self._auth is None:
            from omegacommon.auth import OmegaRuntimeAuthentication
            kwargs = dict(userid=getattr(defaults, 'OMEGA_USERID'),
                          apikey=getattr(defaults, 'OMEGA_APIKEY'),
                          qualifier=getattr(defaults, 'OMEGA_QUALIFIER', 'default'))
            self._auth = OmegaRuntimeAuthentication(**kwargs)
        return self._auth

    @property
    def auth_tuple(self):
        auth = self.auth
        return auth.userid, auth.apikey, auth.qualifier
