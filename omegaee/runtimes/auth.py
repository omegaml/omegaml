from datetime import datetime

from omegaml import session_cache
from omegaml.client.auth import CloudClientAuthenticationEnv, OmegaRuntimeAuthentication


class CloudRuntimeAuthenticationEnv(CloudClientAuthenticationEnv):
    @classmethod
    @session_cache
    def get_omega_for_task(cls, task, auth=None):
        """
        magic sauce to get omegaml for this task without exposing the __auth kwarg

        This links back to omegaml.get_omega_for_task which is
        an injected dependency. This way we can have any authentication
        environment we want. The way this works behind the scenes
        is that the task is passed the __auth kwargs which must hold
        serialized credentials that the get_omega_for_task implementation
        can unwrap, verify the credentials and return an authenticated
        Omega instance. This may seem a little contrived but it allows for
        flexibility.

        Note get_omega_for_task will pop the __auth kwarg so that client
        code never gets to see what it was.

        Returns:
                authenticted Omega instance
        """
        from omegaml import link
        auth = auth or task.system_kwargs.get('__auth')
        om = super().get_omega_for_task(task, auth=auth)
        # link omegaml default instance so import omegaml as om is linked
        # to this instance
        link(om)
        return om


class JWTOmegaRuntimeAuthentation(OmegaRuntimeAuthentication):
    def __init__(self, token, qualifier='default'):
        self.userid = 'jwt'
        self.apikey = token
        self.qualifier = qualifier


class JWTCloudRuntimeAuthenticationEnv(CloudRuntimeAuthenticationEnv):
    @classmethod
    def get_runtime_auth(cls, defaults=None, om=None):
        from jwt_auth import mixins
        from jwt_auth.exceptions import AuthenticationFailed
        # expect a jwt token for runtime authentication
        assert defaults or om, "require either defaults or om"
        defaults = defaults or om.defaults
        token = defaults.OMEGA_APIKEY
        # verify the token is valid
        try:
            payload = mixins.get_payload_from_token(token)
            userid = mixins.jwt_get_user_id_from_payload(payload)
        except AuthenticationFailed:
            raise
        return JWTOmegaRuntimeAuthentation(token,
                                           defaults.OMEGA_QUALIFIER)


def _create_jwt_token(defaults=None, om=None):
    # use for testing only
    from django.conf import settings
    from jwt_auth import settings as jwt_auth_settings

    defaults = defaults or om.defaults
    payload = {
        "username": defaults.OMEGA_USERID,
        "exp": datetime.utcnow() + settings.JWT_EXPIRATION_DELTA,
    }
    token = jwt_auth_settings.JWT_ENCODE_HANDLER(payload)
    return token
