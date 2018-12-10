class AuthenticationEnv(object):
    @classmethod
    def get_omega_for_task(cls, auth=None):
        from omegaml import Omega
        om = Omega()
        return om

    @classmethod
    def get_omega_from_apikey(cls, *args, **kwargs):
        from omegaml import Omega
        om = Omega()
        return om


def get_omega_for_task(*args, **kwargs):
    # legacy wrapper
    from omegaml import settings
    from omegaml.util import load_class
    defaults = settings()
    auth = load_class(defaults.OMEGA_AUTH_ENV)
    return auth.get_omega_for_task(*args, **kwargs)
