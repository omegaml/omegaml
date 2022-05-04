import requests
from jupyterhub.auth import Authenticator
from omegaml import settings
from omegaml.client.auth import AuthenticationEnv


class OmegaAuthenticator(Authenticator):
    async def authenticate(self, handler, data):
        username = data['username']
        password = data['password']
        defaults = settings()
        auth_env = AuthenticationEnv.secure()
        try:
            configs = auth_env.get_userconfig_from_api(userid=username,
                                                       apikey=password,
                                                       defaults=defaults)
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
