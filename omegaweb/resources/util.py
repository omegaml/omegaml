class BundleObj(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


isTrue = lambda v: v if isinstance(v, bool) else (
      v.lower() in ['yes', 'y', 't', 'true', '1'])


def get_omega_for_user(user, qualifier=None, view=False):
    """
    Return an Omega instance configured for the user

    :param user: User object to get omega instance for
    :param qualifier: qualifier, defaults to 'default'
    :param view: if True return the internal MONGO_URL
    """
    from omegaml import Omega
    from omegaops import get_client_config
    from omegaml.client.auth import OmegaRuntimeAuthentication
    from omegaml import settings, _base_config

    # this is the server-side equivalent of omegaml.client.userconf.get_omega_from_apikey
    # note however we don't load any frameworks as omegaweb is supposed to use the runtime
    defaults = settings()
    config = get_client_config(user, qualifier=qualifier, view=view)
    _base_config.update_from_dict(config, attrs=defaults)
    _base_config.update_from_config(defaults)
    _base_config.load_user_extensions(defaults)
    auth = OmegaRuntimeAuthentication(user.username, user.api_key.key)
    om = Omega(defaults=defaults, auth=auth)
    return om
