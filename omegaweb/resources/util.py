from omegacommon.auth import OmegaRuntimeAuthentication


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
    config = get_client_config(user, qualifier=qualifier, view=view)
    mongo_url = config.get('OMEGA_MONGO_URL')
    auth = OmegaRuntimeAuthentication(user.username, user.api_key.key)
    om = Omega(mongo_url=mongo_url,
               auth=auth,
               celeryconf=config.get('OMEGA_CELERY_CONFIG'))
    return om
