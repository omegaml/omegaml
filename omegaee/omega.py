from omegaee._version import version
from omegaee.runtimes.runtime import OmegaAuthenticatedRuntime
from omegaml import load_class
from omegaml.client.auth import AuthenticationEnv


def make_enterprise():
    # avoid circular imports from omegaml.__init__
    from omegaml.client.cloud import setup_from_config, OmegaCloud
    from omegaml.omega import OmegaDeferredInstance as CoreOmegaDeferredInstance

    class EnterpriseOmega(OmegaCloud):
        """
        Client API to omegaml

        Provides the following APIs:

        * :code:`datasets` - access to datasets stored in the cluster
        * :code:`models` - access to models stored in the cluster
        * :code:`runtimes` - access to the cluster compute resources
        * :code:`jobs` - access to jobs stored and executed in the cluster
        * :code:`scripts` - access to lambda modules stored and executed in the cluster

        """

        def __init__(self, **kwargs):
            """
            Initialize the client API

            Without arguments create the client API according to the user's
            configuration in :code:`~/omegaml/config.yml`.

            Arguments override the user's configuration.

            :param mongo_url: the fully qualified URI to the mongo database,
            of format :code:`mongodb://user:password@host:port/database`
            :param broker: the celery broker URI
            :param backend: the celery result backend URI
            :param celeryconf: the celery configuration dictionary
            :param celerykwargs: kwargs to create the Celery instance
            """
            super(EnterpriseOmega, self).__init__(**kwargs)

        def _make_runtime(self, celeryconf):
            if getattr(self, 'auth', None) is None:
                auth_env = load_class(self.defaults.OMEGA_AUTH_ENV)
                self.auth = auth_env.get_runtime_auth(defaults=self.defaults)
            return OmegaAuthenticatedRuntime(self, bucket=self.bucket,
                                             defaults=self.defaults,
                                             celeryconf=celeryconf,
                                             auth=self.auth)

        def __repr__(self):
            return 'OmegaEnterprise(mongo_url={})'.format(self.mongo_url)

    class EnterpriseOmegaDeferredInstance(CoreOmegaDeferredInstance):
        """
        A deferred instance of Omega() that is only instantiated on access

        This is to ensure that module-level imports don't trigger instantiation
        of Omega.
        """

        def setup(self, username=None, apikey=None, api_url=None, qualifier=None, view=True):
            qualifier = qualifier or 'default'
            from omegaml.util import settings
            # load defaults
            defaults = settings()
            # get userid, apikey and api url
            username = username or defaults.OMEGA_USERID
            apikey = apikey or defaults.OMEGA_APIKEY
            api_url = api_url or defaults.OMEGA_RESTAPI_URL
            qualifier = qualifier or defaults.OMEGA_QUALIFIER
            # get authentication options
            auth_set_in_config = all(getattr(defaults, k, False) for k in ('OMEGA_USERID', 'OMEGA_APIKEY'))
            auth_default_allowed = bool(defaults.OMEGA_ALLOW_TASK_DEFAULT_AUTH)
            # enable auth and start
            auth_env = AuthenticationEnv.secure()
            if not self.initialized:
                if username and apikey:
                    # we have a username and apikey and this is the first time we initialize
                    self.omega = auth_env.get_omega_from_apikey(username, apikey, api_url=api_url,
                                                                qualifier=qualifier, view=view)
                elif auth_default_allowed or auth_set_in_config:
                    # if valid userid and apikey set in config, or default config allowed (e.g. testing)
                    self.omega = Omega(defaults=defaults)
                else:
                    try:
                        self.omega = setup_from_config()
                    except:
                        # not allowed if we don't have a userid nor allow the default config
                        raise ValueError('EnterpriseOmegaDeferredInstance: unauthenticated omega is not supported')
                self.initialized = True
            return self

    def setup(username=None, apikey=None, api_url=None, qualifier=None, bucket=None, view=None):
        """
        configure and return the omega client instance

        Usage:
            # example 1
            om.setup(...)
            om.datasets.list()

            # example 2
            myomega = om.setup(...)
            myomega.list()

        Notes:
            Username and apikey are provided, request the user's configuration from the
            configuration site (api_url). If qualifier is provided and the user has been
            authorized for this qualifier the respective configuration is used.

            If username and apikey are not provided the default configuration as per local
            configuration will be returned. Note that the default configuration depends on
            the configuration file in $HOME/.omegaml/config.yml (if present), or the
            system-wide defaults. Typically the system-wide defaults return an instance
            for all-local use, i.e. local database and a single-threaded local runtimes.

            If api_url is not provided, it will default to the system-wide defaults (typically
            http://localhost in test, http://omegaml.omegaml.io for omegaml SaaS provision or
            your on-premise omegaml deployment URL.

        :param username: the username
        :param apikey: the apikey
        :param api_url: the api_url
        :param qualifier: the qualifier. defaults to 'default'
        :param view: if True returns cluster-internal URLs
        :return: the Omega instance
        """
        from omegaml import settings
        defaults = settings()
        view = view if view is not None else defaults.OMEGA_SERVICES_INCLUSTER
        kwargs = dict(username=username,
                      apikey=apikey,
                      api_url=api_url,
                      qualifier=qualifier, view=view)
        # if we don't have a global instance yet, initialize it
        if not _om.initialized:
            return _om.setup(**kwargs).omega[bucket]
        # otherwise return a new instance. use this to open a second instance for
        # another user/apikey or qualifier
        om = EnterpriseOmegaDeferredInstance()
        return om.setup(**kwargs).omega[bucket]

    return EnterpriseOmega, EnterpriseOmegaDeferredInstance, setup


# exports -- these are dependency-injected in omegaml.__init__
EnterpriseOmega, EnterpriseOmegaDeferredInstance, setup = make_enterprise()
OmegaDeferredInstance = EnterpriseOmegaDeferredInstance
Omega = EnterpriseOmega
_om = EnterpriseOmegaDeferredInstance()
version = version  # ensure we keep imports
