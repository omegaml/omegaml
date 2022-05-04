from omegaml import session_cache
from omegaml.client.auth import CloudClientAuthenticationEnv, AuthenticationEnv


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
        auth = task.system_kwargs.get('__auth')
        return super().get_omega_for_task(task, auth=auth)
