from ._version import version


class Omega(object):
    """
    Client API to omegaml

    Provides the following APIs:

    * :code:`datasets` - access to datasets stored in the cluster
    * :code:`models` - access to models stored in the cluster
    * :code:`runtimes` - access to the cluster compute resources
    * :code:`jobs` - access to jobs stored and executed in the cluster
    * :code:`scripts` - access to lambda modules stored and executed in the cluster

    """

    def __init__(self, mongo_url=None, backend=None, broker=None,
                 celeryconf=None, defaults=None):
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
        from omegaml.util import settings
        # avoid circular imports
        from omegaml.notebook.jobs import OmegaJobs
        from omegaml.runtimes import OmegaRuntime
        from omegaml.store import OmegaStore
        # celery and mongo configuration
        self.defaults = defaults or settings()
        self.mongo_url = mongo_url or self.defaults.OMEGA_MONGO_URL
        self.broker = broker or self.defaults.OMEGA_BROKER
        self.backend = backend or self.defaults.OMEGA_RESULT_BACKEND
        self.celeryconf = celeryconf
        # setup storage locations
        self.models = OmegaStore(mongo_url=mongo_url, prefix='models/', defaults=self.defaults)
        self.datasets = OmegaStore(mongo_url=mongo_url, prefix='data/', defaults=self.defaults)
        self._jobdata = OmegaStore(mongo_url=mongo_url, prefix='jobs/', defaults=self.defaults)
        # runtimes environments
        self.runtime = OmegaRuntime(self, backend=backend,
                                    broker=broker, celeryconf=celeryconf,
                                    defaults=self.defaults)
        self.jobs = OmegaJobs(store=self._jobdata)

    def __repr__(self):
        return 'Omega(mongo_url={})'.format(self.mongo_url)


class OmegaDeferredInstance(object):
    """
    A deferred instance of Omega() that is only instantiated on access

    This is to ensure that module-level imports don't trigger instantiation
    of Omega.
    """

    def __init__(self, base=None, attribute=None):
        self.omega = 'not initialized -- call .setup() or access an attribute'
        self.initialized = False
        self.base = base
        self.attribute = attribute

    def setup(self):
        self.omega = Omega()
        self.initialized = True
        return self

    def __getattr__(self, name):
        if self.base:
            base = getattr(self.base, self.attribute)
            return getattr(base, name)
        if not self.initialized:
            self.setup()
        return getattr(self.omega, name)

    def __repr__(self):
        if self.base:
            return repr(getattr(self.base, self.attribute))
        self.setup()
        return repr(self.omega)


def setup():
    """
    configure and return the omega client instance
    """
    return _om.setup().omega

# dynamic lookup of Omega instance in a task context
get_omega_for_task = lambda args: _om

# default instance
# -- these are deferred instanced that is the actual Omega instance
#    is only created on actual attribute access
_om = OmegaDeferredInstance()
version = version  # ensure we keep imports
