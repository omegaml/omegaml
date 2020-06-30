# source https://djangosnippets.org/snippets/2727/
import os

from requests.auth import AuthBase


class AuthenticationEnv(object):
    @classmethod
    def get_omega_for_task(cls, auth=None):
        from omegaml import Omega
        om = Omega()
        return om

    @classmethod
    def get_omega_from_apikey(cls, *args, **kwargs):
        from omegaml import Omega
        om = Omega()
        return om


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
        self.apikey = apikey
        self.qualifier = qualifier or 'default'

    @classmethod
    def make_from(cls, om):
        args = getattr(om.runtime, 'auth_tuple', (None, None, 'default'))
        return OmegaRestApiAuth(*args)

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
    The runtimes authentication
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

        If auth is the tuple (None, None, 'default') the omegaml module
        is returned, which is configured to the default instance with
        authentication according to the installation. To raise an
        error instead set settings OMEGA_ALLOW_TASK_DEFAULT_AUTH=False

        :param auth: the OmegaRuntimeAuthentication object
        :return: the Omega instance configured for the user
        """
        from omegaml.util import settings

        default_auth = (None, None, 'default')
        is_auth_provided = lambda auth: (auth is not None
                                         and auth != default_auth)
        defaults = settings()

        if is_auth_provided(auth):
            if isinstance(auth, (list, tuple)):
                # we get a serialized tuple, recreate auth object
                # -- this is a hack to easily support python 2/3 client/server mix
                userid, apikey, qualifier = auth
                # by default assume worker is in cluster
                # TODO refactor this setting to eedefaults
                view = defaults.OMEGA_WORKER_INCLUSTER
                om = cls.get_omega_from_apikey(userid, apikey, qualifier=qualifier, view=view)
            else:
                raise ValueError(
                    'cannot parse authentication as {}'.format(auth))
        elif auth == default_auth:
            # we provide the default implementation as per configuration
            from omegaml import _omega
            om = _omega._om
            if not defaults.OMEGA_ALLOW_TASK_DEFAULT_AUTH:
                raise ValueError(
                    'Default task authentication is not allowed, got {}'.format(auth))
        else:
            raise ValueError(
                'missing authentication tuple as (userid, apikey, qualifier), got {}'.format(auth))
        return om

    @classmethod
    def get_omega_from_apikey(cls, *args, **kwargs):
        from omegaml.client.userconf import get_omega_from_apikey
        return get_omega_from_apikey(*args, **kwargs)

isTrue = lambda v: v if isinstance(v, bool) else (
    v.lower() in ['yes', 'y', 't', 'true', '1'])
