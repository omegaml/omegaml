from omegacommon.userconf import get_omega_from_apikey


def get_omega_for_task(auth=None):
    """
    Get Omega instance configured for user in auth

    If auth is passed, a request is made to OMEGA_RESTAPI_URL to
    retrieve the configuration object for this user. 

    :param auth: the OmegaRuntimeAuthentication object
    :return: the Omega instance configured for the user
    """
    import omegaml as omdefault
    if auth is not None:
        if isinstance(auth, (list, tuple)):
            # we get a serialized tuple, recreate auth object
            # -- this is a hack to easily support python 2/3 client/server mix
            userid, apikey = auth
            om = get_omega_from_apikey(userid, apikey)
    else:
        om = omdefault
    return om
