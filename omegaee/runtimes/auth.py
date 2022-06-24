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
        auth = auth or task.system_kwargs.get('__auth')
        return super().get_omega_for_task(task, auth=auth)


class JWTOmegaRuntimeAuthentation(OmegaRuntimeAuthentication):
    def __init__(self, token, qualifier='default'):
        self.userid = 'jwt'
        self.apikey = token
        self.qualifier = qualifier


class JWTCloudRuntimeAuthenticationEnv(CloudRuntimeAuthenticationEnv):
    @classmethod
    def get_runtime_auth(cls, defaults=None, om=None):
        # use a jwt token for runtime authentication
        assert defaults or om, "require either defaults or om"
        from django.conf import settings
        from jwt_auth import settings as jwt_auth_settings

        defaults = defaults or om.defaults
        payload = {
            "username": defaults.OMEGA_USERID,
            "exp": datetime.utcnow() + settings.JWT_EXPIRATION_DELTA,
        }
        token = jwt_auth_settings.JWT_ENCODE_HANDLER(payload)
        return JWTOmegaRuntimeAuthentation(token,
                                           defaults.OMEGA_QUALIFIER)
