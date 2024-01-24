import json
import os
import sys
import warnings
import yaml
from urllib3 import Retry

from omegaml import _base_config
from omegaml.client.auth import AuthenticationEnv
from omegaml.util import sec_validate_url

default_key = 'OMEGA_RESTAPI_URL'
fallback_url = 'https://hub.omegaml.io'


def ensure_api_url(api_url, defaults, key=default_key, fallback=fallback_url):
    api_url_default = os.environ.get(key) or os.environ.get(default_key) or fallback
    api_url = api_url or getattr(defaults, key, getattr(defaults, default_key, api_url_default))
    allow_test_local = _base_config.is_test_run and not api_url.startswith('http')
    valid_url = sec_validate_url(api_url) if not allow_test_local else api_url == 'local'
    assert valid_url, f"expected a valid url, got {api_url}"
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


def _get_userconfig_from_api(api_auth, api_url=None, requested_userid=None, qualifier=None, view=False):
    # safe way to talk to either the remote API or the in-process test server
    from omegaml import settings
    from omegaml import _base_config
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
    if _base_config.is_test_run or api_url.startswith('/'):
        try:
            from tastypie.test import TestApiClient
        except ModuleNotFoundError as e:
            # we need omegaee environment to proceed
            raise
        server = TestApiClient()
        server.close = lambda: None
        server_kwargs = dict(authentication=api_auth.get_credentials())
        deserialize = lambda resp: json.loads(resp.content.decode('utf-8'))
    elif api_url.startswith('http'):
        import requests
        server = session_backoff()
        server_kwargs = dict(auth=api_auth)
        deserialize = lambda resp: resp.json()
    else:
        raise ValueError('invalid api_url >{}<'.format(api_url))
    # -- actual logic to get configs
    fail_msg = ("omegaml hub refused authentication by {api_auth}, "
                "status code={resp.status_code} "
                "using {api_url}.")
    resp = server.get(api_url, **server_kwargs)
    assert resp.status_code == 200, fail_msg.format(**locals())
    configs = deserialize(resp)
    server.close()
    return configs


# FIXME enable cache by arguments (mnemonic) @cached(seconds=3600)
def get_omega_from_apikey(*args, **kwargs):
    warnings.warn(('Calling get_omega_from_apikey directly is deprecated '
                   'and will be removed in the next release. Please use  '
                   'AuthenticationEnv.secure().get_omega_from_apikey'), DeprecationWarning)
    return _get_omega_from_apikey(*args, **kwargs)


def _get_omega_from_apikey(userid, apikey, api_url=None, requested_userid=None,
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
    defaults.OMEGA_USERID = userid
    defaults.OMEGA_APIKEY = apikey
    defaults.OMEGA_QUALIFIER = qualifier
    api_url = ensure_api_url(api_url, defaults)
    auth_env = AuthenticationEnv.secure()
    if api_url.startswith('http') or any('test' in v for v in sys.argv):
        configs = auth_env.get_userconfig_from_api(requested_userid=requested_userid,
                                                   api_url=api_url, view=view,
                                                   defaults=defaults)
        configs = configs['objects'][0]['data']
    elif api_url == 'local':
        configs = {k: getattr(defaults, k) for k in dir(defaults) if k.startswith('OMEGA')}
    else:
        raise ValueError('invalid api_url >{}<'.format(api_url))
    config = configs.get(qualifier, configs)
    # update
    _base_config.update_from_dict(config, attrs=defaults)
    _base_config.update_from_config(defaults)
    _base_config.update_from_env(defaults)
    _base_config.load_framework_support(defaults)
    _base_config.load_user_extensions(defaults)
    # update config to reflect request (never update from env or received config)
    defaults.OMEGA_RESTAPI_URL = api_url
    defaults.OMEGA_USERID = userid
    defaults.OMEGA_APIKEY = apikey
    defaults.OMEGA_QUALIFIER = qualifier
    auth = auth_env.get_runtime_auth(defaults)
    om = OmegaCloud(defaults=defaults, auth=auth)
    return om


def get_omega_from_config(*args, **kwargs):
    warnings.warn(('Calling _get_omega_from_config directly is deprecated '
                   'and will be removed in the next release. Please use  '
                   'AuthenticationEnv.secure()._get_omega_from_config'), DeprecationWarning)
    return _get_omega_from_config(*args, **kwargs)


def _get_omega_from_config(configfile, qualifier=None):
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


def _save_userconfig_from_apikey(configfile, userid, apikey, api_url=None, requested_userid=None,
                                 view=False, keys=None, qualifier=None):
    from omegaml import settings
    defaults = settings()
    api_url = ensure_api_url(api_url, defaults)
    required_keys = ['OMEGA_USERID', 'OMEGA_APIKEY', 'OMEGA_RESTAPI_URL', 'OMEGA_QUALIFIER']
    keys = keys or []
    auth_env = AuthenticationEnv.secure()
    with open(configfile, 'w') as fconfig:
        configs = auth_env.get_userconfig_from_api(api_url=api_url,
                                                   userid=userid,
                                                   apikey=apikey,
                                                   requested_userid=requested_userid,
                                                   qualifier=qualifier,
                                                   view=view)
        config = configs['objects'][0]['data']
        config['OMEGA_RESTAPI_URL'] = api_url
        config['OMEGA_QUALIFIER'] = qualifier or 'default'
        config['OMEGA_USERID'] = userid
        config['OMEGA_APIKEY'] = apikey
        config = {
            k: v for k, v in config.items() if k in (required_keys + keys)
        }
        yaml.safe_dump(config, fconfig, default_flow_style=False)
        print("Config is in {configfile}".format(**locals()))
