from omegaee.runtimes.runtime import OmegaAuthenticatedRuntime
from omegajobs.jobs import OmegaEnterpriseJobs
from omegaml.omega import Omega as CoreOmega, OmegaDeferredInstance as CoreOmegaDeferredInstance
from ._version import version


class EnterpriseOmega(CoreOmega):
    """
    Client API to omegaml

    Provides the following APIs:

    * :code:`datasets` - access to datasets stored in the cluster
    * :code:`models` - access to models stored in the cluster
    * :code:`runtimes` - access to the cluster compute resources
    * :code:`jobs` - access to jobs stored and executed in the cluster
    * :code:`scripts` - access to lambda modules stored and executed in the cluster

    """

    def __init__(self, celerykwargs=None, auth=None, **kwargs):
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
        # avoid circular imports
        from omegaml.store import OmegaStore

        # store inputs for reference
        self.auth = auth
        self.celerykwargs = kwargs

        # enterprise extensions
        self.scripts = OmegaStore(mongo_url=self.mongo_url, prefix='scripts/', defaults=self.defaults)
        self.runtime = OmegaAuthenticatedRuntime(self, backend=self.backend,
                                                 auth=self.auth,
                                                 broker=self.broker,
                                                 celeryconf=self.celeryconf,
                                                 celerykwargs=self.celerykwargs,
                                                 defaults=self.defaults)
        self.jobs = OmegaEnterpriseJobs(store=self._jobdata)

    def __repr__(self):
        return 'OmegaEnterprise(mongo_url={})'.format(self.mongo_url)


class EnterpriseOmegaDeferredInstance(CoreOmegaDeferredInstance):
    """
    A deferred instance of Omega() that is only instantiated on access

    This is to ensure that module-level imports don't trigger instantiation
    of Omega.
    """

    def setup(self, username=None, apikey=None, api_url=None, qualifier=None):
        qualifier = qualifier or 'default'
        from omegaml.util import settings, load_class
        defaults = settings()
        auth = load_class(defaults.OMEGA_AUTH_ENV)
        if not self.initialized and username and apikey:
            self.omega = auth.get_omega_from_apikey(username, apikey, api_url=api_url, qualifier=qualifier)
        else:
            self.omega = Omega()
        self.initialized = True
        return self


def setup(username=None, apikey=None, api_url=None, qualifier=None):
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
    :return: the Omega instance
    """
    return _om.setup(username=username, apikey=apikey, api_url=api_url, qualifier=qualifier).omega


def get_omega_for_task(task):
    """
    magic sauce to get omegaml for this task without exposing the __auth kwarg

    This links back to omegaml.get_omega_for_task which is
    an injected dependency. This way we can have any authentication
    environment we want. The way this works behind the scenes
    is that the task is passed the __auth kwargs which must hold
    serialized credentials that the get_omega_for_task implementation
    can unwrap, verify the credentials and return an authenticated
    Omega instance. This may seem a little contrived but it allows for
    flexibility.

    Note get_omega_for_task will pop the __auth kwarg so that client
    code never gets to see what it was.

    Returns:
            authenticted Omega instance
    """
    from omegaml import settings, load_class
    defaults = settings()
    auth_env = load_class(defaults.OMEGA_AUTH_ENV)
    task_kwargs = task.request.kwargs
    auth = task_kwargs.pop('__auth', None)
    return auth_env.get_omega_for_task(auth=auth)


# exports
Omega = EnterpriseOmega
OmegaDeferredInstance = EnterpriseOmegaDeferredInstance
_om = EnterpriseOmegaDeferredInstance()
version = version  # ensure we keep imports
