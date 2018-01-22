
from omegacli.auth import OmegaRestApiAuth
from omegaml import defaults


class OmegaRuntimeAuthentication:

    """
    The runtime authentication
    """

    def __init__(self, userid, apikey):
        self.userid = userid
        self.apikey = apikey


def get_user_config_from_api(api_auth):
    # safe way to talk to either the remote API or the in-process test server
    api_url = defaults.OMEGA_RESTAPI_URL + '/api/v1/config/'
    # -- setup appropriate client API
    if defaults.OMEGA_RESTAPI_URL.startswith('http'):
        import requests
        server = requests
        server_kwargs = dict(auth=api_auth)
        deserialize = lambda resp: resp.json()
    else:
        import json
        from tastypie.test import TestApiClient
        server = TestApiClient()
        server_kwargs = dict(authentication=api_auth.get_credentials())
        deserialize = lambda resp: json.loads(resp.content.decode('utf-8'))
    # -- actual logic to get configs
    fail_msg = ("Not authenticated using userid {api_auth.username}"
                " apikey {api_auth.apikey}, error was {resp.status_code}, "
                "{resp.content}")
    resp = server.get(api_url, **server_kwargs)
    assert resp.status_code == 200, fail_msg.format(**locals())
    configs = deserialize(resp)
    return configs


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
        api_auth = OmegaRestApiAuth(auth.userid,
                                    auth.apikey)
        configs = get_user_config_from_api(api_auth)
        config = configs['objects'][0]['data']
        mongo_url = config['OMEGA_MONGO_URL']
        om = omdefault.Omega(mongo_url=mongo_url)
    else:
        om = omdefault
    return om
