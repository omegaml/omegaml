from omegacommon.userconf import get_omega_from_apikey


def get_omega_for_task(auth=None):
    """
    Get Omega instance configured for user in auth

    If auth is passed, a request is made to OMEGA_RESTAPI_URL to
    retrieve the configuration object for this user. 

    :param auth: the OmegaRuntimeAuthentication object
    :return: the Omega instance configured for the user
    """
    is_auth_provided = lambda auth: (auth is not None
                                     and (None, None, 'default') != auth)
    if is_auth_provided(auth):
        if isinstance(auth, (list, tuple)):
            # we get a serialized tuple, recreate auth object
            # -- this is a hack to easily support python 2/3 client/server mix
            userid, apikey, qualifier = auth
            om = get_omega_from_apikey(userid, apikey, qualifier=qualifier)
        else:
            raise ValueError(
                'cannot parse authentication as {}'.format(auth))
    else:
        from omegaml import Omega
        om = Omega()
    return om
