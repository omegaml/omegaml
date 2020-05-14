from ._version import version
from .store.logging import OmegaSimpleLogger


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

    def __init__(self, defaults=None, mongo_url=None, celeryconf=None, bucket=None,
                 **kwargs):
        """
        Initialize the client API

        Without arguments create the client API according to the user's
        configuration in :code:`~/omegaml/config.yml`.

        Arguments override the user's configuration.

            :param defaults: the DefaultsContext
        :param mongo_url: the fully qualified URI to the mongo database,
        of format :code:`mongodb://user:password@host:port/database`
        :param celeryconf: the celery configuration dictionary
        """
        from omegaml.util import settings
        # avoid circular imports
        from omegaml.notebook.jobs import OmegaJobs
        from omegaml.store import OmegaStore
        # celery and mongo configuration
        self.defaults = defaults or settings()
        self.mongo_url = mongo_url or self.defaults.OMEGA_MONGO_URL
        self.bucket = bucket
        # setup storage locations
        self.models = OmegaStore(mongo_url=self.mongo_url, bucket=bucket, prefix='models/', defaults=self.defaults)
        self.datasets = OmegaStore(mongo_url=self.mongo_url, bucket=bucket, prefix='data/', defaults=self.defaults)
        self._jobdata = OmegaStore(mongo_url=self.mongo_url, bucket=bucket, prefix='jobs/', defaults=self.defaults)
        self.scripts = OmegaStore(mongo_url=self.mongo_url, prefix='scripts/', defaults=self.defaults)
        # runtimes environments
        self.runtime = self._make_runtime(celeryconf)
        self.jobs = OmegaJobs(store=self._jobdata)
        # logger
        self.logger = OmegaSimpleLogger(store=self.datasets, defaults=self.defaults)

    def __repr__(self):
        return 'Omega()'.format()

    def _clone(self, **kwargs):
        return self.__class__(defaults=self.defaults,
                              mongo_url=self.mongo_url,
                              **kwargs)

    def _make_runtime(self, celeryconf):
        from omegaml.runtimes import OmegaRuntime
        return OmegaRuntime(self, bucket=self.bucket, defaults=self.defaults, celeryconf=celeryconf)

    def __getitem__(self, bucket):
        """
        return Omega instance configured for the given bucket

        Args:
            bucket (str): the bucket name. If it does not exist
                  it gets created on first storage of an object.
                  If bucket=None returns self.

        Usage:
            import omegaml as om

            # om is configured on the default bucket
            # om_mybucket will use the same settings, but configured for mybucket
            om_mybucket = om['mybucket']

        Returns:
            Omega instance configured for the given bucket
        """
        if bucket is None or self.bucket == bucket:
            return self
        return self._clone(bucket=bucket)


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

    def setup(self, mongo_url=None, bucket=None, celeryconf=None):
        from omegaml.client.cloud import setup_from_config
        try:
            omega = setup_from_config()
        except SystemError:
            omega = Omega(mongo_url=None, bucket=bucket, celeryconf=None)
        if not self.initialized:
            self.initialized = True
            self.omega = omega
        return omega

    def __getattr__(self, name):
        if self.base:
            base = getattr(self.base, self.attribute)
            return getattr(base, name)
        if not self.initialized:
            self.setup()
        return getattr(self.omega, name)

    def __getitem__(self, bucket):
        if self.base:
            base = getattr(self.base, self.attribute)
            return base[bucket]
        if not self.initialized:
            self.setup()
        return self.omega[bucket]

    def __repr__(self):
        if self.base:
            return repr(getattr(self.base, self.attribute))
        self.setup()
        return repr(self.omega)


def setup(*args, **kwargs):
    """
    configure and return the omega client instance
    """
    return _om.setup(*args, **kwargs)


# dynamic lookup of Omega instance in a task context
get_omega_for_task = lambda *args, **kwargs: _om.setup(*args, **kwargs)

# default instance
# -- these are deferred instanced that is the actual Omega instance
#    is only created on actual attribute access
_om = OmegaDeferredInstance()
version = version  # ensure we keep imports
