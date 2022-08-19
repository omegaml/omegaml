from requests.auth import AuthBase

from omegaml import session_cache
from omegaml.util import load_class, settings


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

    def get_credentials(self):
        if self.username != 'jwt':
            return 'ApiKey %s:%s' % (self.username, self.apikey)
        else:
            return 'Bearer %s' % (self.apikey,)

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

    @property
    def token(self):
        return self.userid, self.apikey, self.qualifier

    def __repr__(self):
        return ('OmegaRuntimeAuthentication(userid={}, '
                'apikey="*****", qualifier={})').format(self.userid, self.qualifier)




class AuthenticationEnv(object):
    """ AuthenticationEnv creates Omega() configured to the current environment

    This provides a basic authentication environment that is not protected. It
    should not be used in production environments.

    Usage::

        auth_env = AuthenticationEnv.active()
        om = auth_env.get_omega_from_apikey(<credentials>)
        om = auth_env.get_omega_for_task(task, auth=<credentials>)

    Notes:
        * AuthenticationEnv.active() returns the environment as configured
          in defaults.OMEGA_AUTH_ENV. This defaults to AuthenticationEnv.
        * Any AuthenticationEnv is required to provide at least
          get_omega_from_apikey() and get_omega_from_task() methods, as
          the primary ways to instantiate omega is from either a set of
          credentials (userid, apikey), or from a an authorized task that
          provides these credentials
        * some authentication environments may require additional methods
          to provide credentials in a format suitable for their authentication
          backends (e.g. REST APIs, kerberos, etc.)
    """
    auth_env = None
    is_secure = False

    @classmethod
    @session_cache  # PERFTUNED
    def get_omega_for_task(cls, task, auth=None):
        # return the omega instance for the given task authentication
        from omegaml import setup
        om = setup()
        return om

    @classmethod
    @session_cache  # PERFTUNED
    def get_omega_from_apikey(cls, auth=None):
        # return the omega instance for the given task authentication
        from omegaml import setup
        om = setup()
        return om

    @classmethod
    def active(cls):
        # load the currently active auth env
        if cls.auth_env is None:
            from omegaml import _base_config
            cls.auth_env = load_class(getattr(_base_config, 'OMEGA_AUTH_ENV',
                                              'omegaml.client.auth.AuthenticationEnv'))
        return cls.auth_env

    @classmethod
    def secure(cls):
        # load a server-backed authentication env
        from omegaml import _base_config
        if not hasattr(_base_config, 'OMEGA_AUTH_ENV'):
            _base_config.OMEGA_AUTH_ENV = 'omegaml.client.auth.CloudClientAuthenticationEnv'
            cls.auth_env = None
        auth_env = cls.active()
        if not auth_env.is_secure:
            raise SystemError(f'A secure authentication environment was requested, however {auth_env} is not secure.')
        return auth_env


class CloudClientAuthenticationEnv(AuthenticationEnv):
    is_secure = True

    @classmethod
    @session_cache
    def get_omega_for_task(cls, task, auth=None):
        """
        Get Omega instance configured for user in auth

        If auth is passed, a request is made to OMEGA_RESTAPI_URL to
        retrieve the configuration object for this user.

        If auth is the tuple (None, None, 'default') the omegaml module
        is returned, which is configured to the default instance with
        authentication according to the installation. To raise an
        error instead set settings OMEGA_ALLOW_TASK_DEFAULT_AUTH=False

        :param auth: the OmegaRuntimeAuthentication object, or a token (userid, apikey, qualifier)
        :return: the Omega instance configured for the user
        """
        from omegaml.util import settings

        default_auth = (None, None, 'default')
        is_auth_provided = lambda token: (token is not None
                                         and token != default_auth)
        defaults = settings()
        token = auth.token if isinstance(auth, OmegaRuntimeAuthentication) else auth

        if is_auth_provided(token):
            if isinstance(token, (list, tuple)):
                # we get a serialized tuple, recreate auth object
                # -- this is a hack to easily support python 2/3 client/server mix
                userid, apikey, qualifier = token
                # by default assume worker is in cluster
                # TODO refactor this setting to eedefaults
                view = defaults.OMEGA_SERVICES_INCLUSTER
                om = cls.get_omega_from_apikey(userid, apikey, qualifier=qualifier, view=view)
            else:
                raise ValueError(
                    'cannot parse authentication as {}'.format(auth))
        elif token == default_auth:
            # we provide the default implementation as per configuration
            from omegaml import _omega
            om = _omega._om
            if not getattr(defaults, 'OMEGA_ALLOW_TASK_DEFAULT_AUTH', True):
                raise ValueError(
                    'Default task authentication is not allowed, got {}'.format(auth))
        else:
            raise ValueError(
                'Missing runtime task authentication, got {}'.format(auth))
        return om

    @classmethod
    @session_cache  # PERFTUNED
    def get_omega_from_apikey(cls, *args, **kwargs):
        from omegaml.client.userconf import _get_omega_from_apikey
        return _get_omega_from_apikey(*args, **kwargs)

    @classmethod
    def get_restapi_auth(cls, defaults=None, om=None,
                         userid=None, apikey=None, qualifier=None):
        assert defaults or om, "require either defaults or om"
        defaults = defaults or om.defaults
        return OmegaRestApiAuth(userid or defaults.OMEGA_USERID,
                                apikey or defaults.OMEGA_APIKEY,
                                qualifier or defaults.OMEGA_QUALIFIER)

    @classmethod
    def get_runtime_auth(cls, defaults=None, om=None):
        assert defaults or om, "require either defaults or om"
        defaults = defaults or om.defaults
        return OmegaRuntimeAuthentication(defaults.OMEGA_USERID,
                                          defaults.OMEGA_APIKEY,
                                          defaults.OMEGA_QUALIFIER)

    @classmethod
    def get_userconfig_from_api(cls, api_auth=None, api_url=None, userid=None, apikey=None,
                                requested_userid=None, defaults=None, qualifier=None, view=False):
        from omegaml.client.userconf import _get_userconfig_from_api, ensure_api_url
        defaults = defaults or settings()
        api_auth = api_auth or cls.get_restapi_auth(userid=userid, apikey=apikey,
                                                    qualifier=qualifier,
                                                    defaults=defaults)
        return _get_userconfig_from_api(api_auth,
                                        api_url=ensure_api_url(api_url, defaults),
                                        qualifier=qualifier or defaults.OMEGA_QUALIFIER,
                                        requested_userid=requested_userid,
                                        view=view)

    @classmethod
    def save_userconfig_from_apikey(cls, configfile, userid, apikey, api_url=None, requested_userid=None,
                                    view=False, keys=None, qualifier=None):
        from omegaml.client.userconf import _save_userconfig_from_apikey
        return _save_userconfig_from_apikey(configfile, userid, apikey, api_url=api_url,
                                            requested_userid=requested_userid,
                                            view=view, keys=keys, qualifier=qualifier)
