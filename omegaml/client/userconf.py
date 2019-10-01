import sys

import yaml

from omegaml import settings
from omegaml.client.auth import OmegaRestApiAuth


def get_user_config_from_api(api_auth, api_url=None, requested_userid=None, view=False):
    # safe way to talk to either the remote API or the in-process test server
    defaults = settings()
    api_url = api_url or defaults.OMEGA_RESTAPI_URL
    api_url += '/api/v1/config/'
    api_url = api_url.replace('//api', '/api')
    query = []
    if requested_userid:
        query.append('user={}'.format(requested_userid))
    if view:
        query.append('view={}'.format(int(view)))
    api_url += '?' + '&'.join(query)
    # -- setup appropriate client API
    if api_url.startswith('http'):
        import requests
        server = requests
        server_kwargs = dict(auth=api_auth)
        deserialize = lambda resp: resp.json()
    elif any('test' in v for v in sys.argv):
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
                " apikey {api_auth.apikey}, error was {resp.status_code} "
                "using {api_url}\n{resp.content}")
    resp = server.get(api_url, **server_kwargs)
    assert resp.status_code == 200, fail_msg.format(**locals())
    configs = deserialize(resp)
    return configs


#FIXME enable cache by arguments (mnemonic) @cached(seconds=3600)
def get_omega_from_apikey(userid, apikey, api_url=None, requested_userid=None,
                          qualifier=None, view=False):
    """
    setup an Omega instance from userid and apikey

    :param userid: the userid
    :param apikey: the apikey
    :param api_url: the api URL
    :param requested_userid: the userid to request config for. in this case userid
      and apikey must for a staff user for the request to succeed
    :param qualifier: the database qualifier requested. defaults to 'default'
    :returns: the Omega instance configured for the given user
    """
    from omegaml import Omega
    from omegaml import settings, _base_config

    defaults = settings()
    qualifier = qualifier or 'default'
    api_url = api_url or defaults.OMEGA_RESTAPI_URL
    if api_url.startswith('http') or any('test' in v for v in sys.argv):
        api_auth = OmegaRestApiAuth(userid, apikey)
        configs = get_user_config_from_api(api_auth, api_url=api_url,
                                           requested_userid=requested_userid,
                                           view=view)
        configs = configs['objects'][0]['data']
    elif api_url == 'local':
        configs = {k: getattr(defaults, k) for k in dir(defaults) if k.startswith('OMEGA')}
    else:
        raise ValueError('invalid api_url {}'.format(api_url))
    if qualifier == 'default':
        config = configs.get(qualifier, configs)
    else:
        config = configs[qualifier]
    _base_config.update_from_dict(config)
    settings(reload=True)
    om = Omega(defaults=defaults)
    return om


def get_omega_from_config(configfile, qualifier=None):
    from omegaml import Omega
    from omegaml import settings, _base_config
    defaults = settings()
    with open(configfile, 'r') as fconfig:
        configs = yaml.safe_load(fconfig)
    qualifier = qualifier or 'default'
    if qualifier == 'default':
        config = configs.get(qualifier, configs)
    else:
        config = configs[qualifier]
    _base_config.update_from_dict(config)
    settings(reload=True)
    om = Omega(defaults=defaults)
    return om


def save_userconfig_from_apikey(configfile, userid, apikey, api_url=None, requested_userid=None):
    from omegaml import settings
    defaults = settings()
    api_url = api_url or defaults.OMEGA_RESTAPI_URL
    with open(configfile, 'w') as fconfig:
        auth = OmegaRestApiAuth(userid, apikey)
        configs = get_user_config_from_api(auth,
                                           api_url=api_url,
                                           requested_userid=requested_userid)
        config = configs['objects'][0]['data']
        yaml.safe_dump(config, fconfig, default_flow_style=False)
        print("Config is in {configfile}".format(**locals()))
