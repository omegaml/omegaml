import sys

from omegacommon.auth import OmegaRuntimeAuthentication, OmegaRestApiAuth
from omegacommon.util import cached


def get_user_config_from_api(api_auth, api_url=None):
    from omegaml import defaults
    # safe way to talk to either the remote API or the in-process test server
    api_url = api_url or defaults.OMEGA_RESTAPI_URL
    api_url += '/api/v1/config/'.replace('//', '/')
    # -- setup appropriate client API
    if defaults.OMEGA_RESTAPI_URL.startswith('http'):
        import requests
        server = requests
        server_kwargs = dict(auth=api_auth)
        deserialize = lambda resp: resp.json()
    elif 'test' in sys.argv:
        # test support
        import json
        from tastypie.test import TestApiClient
        server = TestApiClient()
        server_kwargs = dict(authentication=api_auth.get_credentials())
        deserialize = lambda resp: json.loads(resp.content.decode('utf-8'))
    else:
        raise ValueError('invalid api_url {}'.format(api_url))
    # -- actual logic to get configs
    fail_msg = ("Not authenticated using userid {api_auth.username}"
                " apikey {api_auth.apikey}, error was {resp.status_code}, "
                "{resp.content}")
    resp = server.get(api_url, **server_kwargs)
    assert resp.status_code == 200, fail_msg.format(**locals())
    configs = deserialize(resp)
    return configs


@cached(seconds=3600)
def get_omega_from_apikey(userid, apikey, api_url=None):
    """
    setup an Omega instance from userid and apikey

    :param userid: the userid
    :param apikey: the apikey
    :param aip_url: the api URL
    :returns: the Omega instance configured for the given user
    """
    from omegaml import Omega, defaults
    api_url = api_url or defaults.OMEGA_RESTAPI_URL
    if api_url.startswith('http') or 'test' in sys.argv:
        api_auth = OmegaRestApiAuth(userid, apikey)
        configs = get_user_config_from_api(api_auth, api_url=api_url)
        config = configs['objects'][0]['data']
    elif api_url == 'local':
        config = {k: getattr(defaults, k) for k in dir(defaults) if k.startswith('OMEGA')}
    else:
        raise ValueError('invalid api_url {}'.format(api_url))
    mongo_url = config['OMEGA_MONGO_URL']
    om = Omega(mongo_url=mongo_url)
    return om
