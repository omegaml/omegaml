import cachetools

from omegaml.client.auth import AuthenticationEnv


class BundleObj(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


isTrue = lambda v: v if isinstance(v, bool) else (
      v.lower() in ['yes', 'y', 't', 'true', '1'])


def get_omega_for_user(user, qualifier=None, view=None, creds=None):
    """
    Return an Omega instance configured for the user

    :param user: User object to get omega instance for
    :param qualifier: qualifier, defaults to 'default'
    :param view: if True return the internal MONGO_URL
    :param creds: the (userid, apikey) or (userid, apikey, qualifier) authentication token
           defaults to (user.userid, user.api_key.key).

    Notes:

        creds will be unpacked to::

            defaults.OMEGA_USERID, defaults.OMEGA_APIKEY, *_ = creds

        defaults is passed to AuthenticationEnv.get_runtime_auth(defaults) to
        set the Omega() runtime authentication
    """
    from omegaml import Omega
    from omegaops import get_client_config
    from omegaml import settings, _base_config, session_cache

    # this is the server-side equivalent of omegaml.client.userconf.get_omega_from_apikey
    # note however we don't load any frameworks as omegaweb is supposed to use the runtime
    defaults = settings(reload=True)
    view = view if view is not None else defaults.OMEGA_SERVICES_INCLUSTER
    config = get_client_config(user, qualifier=qualifier, view=view)
    _base_config.update_from_dict(config, attrs=defaults)
    _base_config.update_from_config(defaults)
    _base_config.load_user_extensions(defaults)
    creds = creds or (user.username, user.api_key.key)
    defaults.OMEGA_USERID, defaults.OMEGA_APIKEY, *_ = creds
    auth_env = AuthenticationEnv.secure()
    auth = auth_env.get_runtime_auth(defaults=defaults)
    # reminder: previously we used OmegaRuntimeAuthentication directly, now replaced by configurable AuthenticationEnv
    # auth = OmegaRuntimeAuthentication(user.username, user.api_key.key, qualifier=qualifier)
    om = Omega(defaults=defaults, auth=auth)
    return om
