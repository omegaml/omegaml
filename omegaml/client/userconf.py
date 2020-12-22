import os
import sys
import yaml
from urllib3 import Retry

import omegaml
from omegaml.client.auth import OmegaRestApiAuth, OmegaRuntimeAuthentication


def ensure_api_url(api_url, defaults):
    api_url_default = os.environ.get('OMEGA_RESTAPI_URL') or 'https://hub.omegaml.io'
    api_url = api_url or getattr(defaults, 'OMEGA_RESTAPI_URL', api_url_default)
    return api_url


def ensure_api_url(api_url, defaults):
    api_url_default = os.environ.get('OMEGA_RESTAPI_URL') or 'https://hub.omegaml.io'
    api_url = api_url or getattr(defaults, 'OMEGA_RESTAPI_URL', api_url_default)
    return api_url


def session_backoff(retries=5):
    import requests
    from requests.adapters import HTTPAdapter
    s = requests.Session()
    retry = Retry(total=retries,
                  backoff_factor=.1,
                  status_forcelist=[500, 502, 503, 504])
    s.mount('http://', HTTPAdapter(max_retries=retry))
    s.mount('https://', HTTPAdapter(max_retries=retry))
    return s


def get_user_config_from_api(api_auth, api_url=None, requested_userid=None, qualifier=None, view=False):
    # safe way to talk to either the remote API or the in-process test server
    from omegaml import settings
    defaults = settings()
    api_url = ensure_api_url(api_url, defaults)
    api_url += '/api/v1/config/'
    api_url = api_url.replace('//api', '/api')
    query = []
    if requested_userid:
        query.append('user={}'.format(requested_userid))
    if view:
        query.append('view={}'.format(int(view)))
    if qualifier:
        query.append('qualifier={}'.format(qualifier))
    api_url += '?' + '&'.join(query)
    # -- setup appropriate client API
    if api_url.startswith('http'):
        import requests
        server = session_backoff()
        server_kwargs = dict(auth=api_auth)
        deserialize = lambda resp: resp.json()
    elif api_url.startswith('test') or any('test' in v for v in sys.argv):
        # test support
        import json
        from tastypie.test import TestApiClient
        server = TestApiClient()
        server.close = lambda : None
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
    server.close()
    return configs


# FIXME enable cache by arguments (mnemonic) @cached(seconds=3600)
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
    :returns: OmegaCloud instance configured for the given user

    Returns:
        OmegaCloud
    """
    from omegaml.client.cloud import OmegaCloud
    from omegaml import settings, _base_config

    defaults = settings(reload=True)
    qualifier = qualifier or 'default'
    api_url = ensure_api_url(api_url, defaults)
    if api_url.startswith('http') or any('test' in v for v in sys.argv):
        api_auth = OmegaRestApiAuth(userid, apikey)
        configs = get_user_config_from_api(api_auth, api_url=api_url,
                                           requested_userid=requested_userid,
                                           view=view, qualifier=qualifier)
        configs = configs['objects'][0]['data']
    elif api_url == 'local':
        configs = {k: getattr(defaults, k) for k in dir(defaults) if k.startswith('OMEGA')}
    else:
        raise ValueError('invalid api_url {}'.format(api_url))
    config = configs.get(qualifier, configs)
    # update
    _base_config.update_from_dict(config, attrs=defaults)
    _base_config.load_framework_support(defaults)
    _base_config.load_user_extensions(defaults)
    auth = OmegaRuntimeAuthentication(userid, apikey, qualifier)
    om = OmegaCloud(defaults=defaults, auth=auth)
    # update config to reflect request
    om.defaults.OMEGA_RESTAPI_URL = api_url
    om.defaults.OMEGA_USERID = userid
    om.defaults.OMEGA_APIKEY = apikey
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
    _base_config.update_from_dict(config, attrs=defaults)
    settings(reload=True)
    om = Omega(defaults=defaults)
    return om


def save_userconfig_from_apikey(configfile, userid, apikey, api_url=None, requested_userid=None,
                                view=False):
    from omegaml import settings
    defaults = settings()
    api_url = ensure_api_url(api_url, defaults)
    with open(configfile, 'w') as fconfig:
        auth = OmegaRestApiAuth(userid, apikey)
        configs = get_user_config_from_api(auth,
                                           api_url=api_url,
                                           requested_userid=requested_userid,
                                           view=view)
        config = configs['objects'][0]['data']
        config['OMEGA_RESTAPI_URL'] = api_url
        yaml.safe_dump(config, fconfig, default_flow_style=False)
        print("Config is in {configfile}".format(**locals()))
