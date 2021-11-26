import requests
from jupyterhub.auth import Authenticator
from omegaml.client.auth import OmegaRestApiAuth
from omegaml.client.userconf import get_user_config_from_api
from tornado import gen

APIKEYS = {}

class OmegaAuthenticator(Authenticator):
    @gen.coroutine
    def authenticate(self, handler, data):
        username = data['username']
        password = data['password']
        APIKEYS[username] = password
        from omegaml import settings
        defaults = settings()
        api_url = defaults.OMEGA_RESTAPI_URL
        api_auth = OmegaRestApiAuth(username, password)
        try:
            configs = get_user_config_from_api(api_auth, api_url=api_url)
            config = configs['objects'][0]['data']
        except:
            return None
        return username


class TokenAuthentication(requests.auth.AuthBase):
    """
    Sets the appropriate authentication headers
    for the JupyterHub token authentication.

    Usage:
        auth = TokenAuthentication('25fdd0d9d210acb78b5b845fe8284a3c93630252')
        response = requests.get('http://jupyterhub/api/...', auth=auth)
    """

    def __init__(self, token):
        self.token = token

    def get_credentials(self):
        return 'token {}'.format(self.token)

    def __call__(self, r):
        r.headers['Authorization'] = self.get_credentials()
        return r

    def __repr__(self):
        return 'TokenAuthentication(token="****")'
