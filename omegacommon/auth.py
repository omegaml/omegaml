# source https://djangosnippets.org/snippets/2727/
from requests.auth import AuthBase

from omegaml.runtime.auth import AuthenticationEnv


class OmegaRestApiAuth(AuthBase):

    """
    Sets the appropriate authentication headers
    for the Omega REST API key authentication.

    Usage:
        auth = OmegaRestApiAuth('jezdez', 
                         '25fdd0d9d210acb78b5b845fe8284a3c93630252')
        response = requests.get('http://api.foo.bar/v1/spam/', auth=auth)
    """
    def __init__(self, username, apikey, qualifier=None):
        self.username = username
        self.\
            apikey = apikey
        self.qualifier = qualifier or 'default'

    def get_credentials(self):
        return 'ApiKey %s:%s' % (self.username, self.apikey)

    def __call__(self, r):
        r.headers['Authorization'] = self.get_credentials()
        r.headers['Qualifier'] = self.qualifier
        return r

    def __repr__(self):
        return ('OmegaRestApiAuth(username={}, apikey="*****",'
                'qualifier={})').format(self.username, self.qualifier)


class OmegaRuntimeAuthentication:

    """
    The runtime authentication
    """

    def __init__(self, userid, apikey, qualifier='default'):
        self.userid = userid
        self.apikey = apikey
        self.qualifier = qualifier

    def __repr__(self):
        return ('OmegaRuntimeAuthentication(userid={}, '
                'apikey="*****", qualifier={})').format(self.userid, self.qualifier)


class OmegaSecureAuthenticationEnv(AuthenticationEnv):
    @classmethod
    def get_omega_for_task(cls, auth=None):
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
                om = cls.get_omega_from_apikey(userid, apikey, qualifier=qualifier)
            else:
                raise ValueError(
                    'cannot parse authentication as {}'.format(auth))
        else:
            from omegaml import Omega
            om = Omega()
        return om

    @classmethod
    def get_omega_from_apikey(cls, *args, **kwargs):
        from omegacommon.userconf import get_omega_from_apikey
        return get_omega_from_apikey(*args, **kwargs)

