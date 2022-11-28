from omegaml import session_cache
from omegaml.client.auth import CloudClientAuthenticationEnv, OmegaRuntimeAuthentication


class CloudRuntimeAuthenticationEnv(CloudClientAuthenticationEnv):
    # make sure this matches OMEGA_* keys in spawnermixin.om_env
    env_keys = ['OMEGA_AUTH_ENV', 'OMEGA_RESTAPI_URL',
                'OMEGA_USERID', 'OMEGA_APIKEY', 'OMEGA_QUALIFIER',
                'OMEGA_SERVICES_INCLUSTER']

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
