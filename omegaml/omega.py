import os
from uuid import uuid4

from omegaml.util import inprogress
from ._version import version
from .mixins.store.requests import CombinedStoreRequestCache
from .store.combined import CombinedOmegaStoreMixin
from .store.logging import OmegaSimpleLogger


class Omega(CombinedStoreRequestCache, CombinedOmegaStoreMixin):
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
        # celery and mongo configuration
        self.defaults = defaults or settings()
        self.mongo_url = mongo_url or self.defaults.OMEGA_MONGO_URL
        self.bucket = bucket
        # setup storage locations
        self._dbalias = self._make_dbalias()
        self.models = self._make_store(prefix='models/')
        self.datasets = self._make_store(prefix='data/')
        self._jobdata = self._make_store(prefix='jobs/')
        self.scripts = self._make_store(prefix='scripts/')
        # minibatch integration
        self.streams = self._make_streams(prefix='streams/')
        # runtimes environments
        self.runtime = self._make_runtime(celeryconf)
        self.jobs = OmegaJobs(store=self._jobdata, defaults=self.defaults)
        # logger
        self.logger = OmegaSimpleLogger(store=self.datasets, defaults=self.defaults)
        # stores
        self._stores = [self.models, self.datasets, self.scripts, self.jobs, self.streams]
        # monitoring
        self._monitor = None  # will be created by .status() on first access

    def __repr__(self):
        return f'Omega(bucket={self.bucket})'

    def _clone(self, **kwargs):
        return self.__class__(defaults=self.defaults,
                              mongo_url=self.mongo_url,
                              **kwargs)

    def _make_runtime(self, celeryconf):
        from omegaml.runtimes import OmegaRuntime
        return OmegaRuntime(self, bucket=self.bucket, defaults=self.defaults, celeryconf=celeryconf)

    def _make_store(self, prefix):
        from omegaml.store import OmegaStore
        return OmegaStore(mongo_url=self.mongo_url, bucket=self.bucket, prefix=prefix, defaults=self.defaults,
                          dbalias=self._dbalias)

    def _make_dbalias(self):
        return 'omega-{}'.format(uuid4().hex)

    def _make_streams(self, prefix):
        from omegaml.store.streams import StreamsProxy
        return StreamsProxy(mongo_url=self.mongo_url, bucket=self.bucket, prefix=prefix, defaults=self.defaults)

    def _make_monitor(self):
        import weakref
        from omegaml.client.lunamon import LunaMonitor, OmegaMonitors
        status_logger = self.runtime.experiment('.system')
        for_keys = lambda event, keys: {k: event[k] for k in keys if k in event}
        on_status = lambda event: (status_logger.use().log_event('monitor', event['check'],
                                                                 for_keys(event,
                                                                          ('status', 'message', 'error',
                                                                           'elapsed')))
                                   if event['check'] == 'health' else None)
        monitor = LunaMonitor(checks=OmegaMonitors.on(self), on_status=on_status, interval=15)
        weakref.finalize(self, monitor.stop)
        return monitor

    def status(self, check=None, data=False, by_status=False, wait=False):
        """ get the status of the omegaml cluster

        Args:
            check (str): the check to run, e.g. 'storage', 'runtime'
            data (bool): return the monitoring data for the check
            by_status (bool): return data by status
            wait (bool): wait for the check to complete

        Returns:
            dict 
        """
        if self._monitor is None:
            # we defer the creation of the monitor to the first access
            # -- this is to avoid creating a monitor for every instance
            # -- e.g. in runtime where the instance is created for short-lived tasks,
            #    the monitor would be created and immediately gc'd
            self._monitor = self._make_monitor()
        if wait:
            self._check_connections()
        return self._monitor.status(check=check, data=data, by_status=by_status)

    def _check_connections(self):
        return self._monitor.wait_ok()

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
        return self._get_bucket(bucket)

    @property
    def buckets(self):
        from itertools import chain
        return list(set(chain(*[getattr(store, 'buckets', []) for store in self._stores])))

    def _get_bucket(self, bucket):
        # enable patching in testing
        if bucket is None or bucket == self.bucket or (bucket == 'default' and self.bucket is None):
            return self
        if bucket == 'default':
            # actual bucket selection is a responsibility of the store, thus we pass None
            # (it is for good reason: OmegaStore should be instantiatable without giving a specific bucket)
            bucket = None
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

    @inprogress(text='loading ...')
    def setup(self, *args, **kwargs):
        """loads omegaml

        Loading order
            - cloud using environment
            - cloud using config file
            - local instance

        Returns:
            omega instance
        """
        from omegaml import _base_config

        @inprogress(text='loading base ...')
        def setup_base():
            from omegaml import _base_config
            _base_config.load_framework_support()
            _base_config.load_user_extensions()
            return Omega(*args, **kwargs)

        @inprogress(text='loading cloud ...')
        def setup_cloud():
            from omegaml.client.cloud import setup
            return setup(*args, **kwargs)

        @inprogress(text='loading cloud from env ...')
        def setup_env():
            from omegaml.client.cloud import setup
            return setup(userid=os.environ['OMEGA_USERID'], apikey=os.environ['OMEGA_APIKEY'],
                         qualifier=os.environ.get('OMEGA_QUALIFIER'))

        @inprogress(text='loading cloud from config ...')
        def setup_cloud_config():
            from omegaml.client.cloud import setup_from_config
            return setup_from_config(fallback=setup_base)

        omega = None
        from_args = len(args) > 0 or any(kw in kwargs for kw in ('userid', 'apikey', 'api_url', 'qualifier'))
        from_env = {'OMEGA_USERID', 'OMEGA_APIKEY'} < set(os.environ)
        from_config = _base_config.OMEGA_CONFIG_FILE and os.path.exists(_base_config.OMEGA_CONFIG_FILE)
        loaders = ((from_args, setup_cloud), (from_env, setup_env),
                   (from_config, setup_cloud_config), (True, setup_base))
        must_load = (from_env, setup_env), (from_config, setup_cloud_config)
        errors = []
        for condition, loader in loaders:
            if not condition:
                continue
            try:
                omega = loader()
            except Exception as e:
                errors.append((loader, e))
                if any(condition and loader is expected for condition, expected in must_load):
                    raise
            else:
                break
        else:
            assert omega is not None, f"failed to load omega due to {errors}"

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

    def __call__(self, *args, **kwargs):
        if self.base:
            base = getattr(self.base, self.attribute)
            return base(*args, **kwargs)
        if not self.initialized:
            self.setup()
        return self(*args, **kwargs)

    @property
    def instance(self):
        return self.base


def setup(*args, **kwargs):
    """
    configure and return the omega client instance
    """
    return _om.setup(*args, **kwargs)


# default instance
# -- these are deferred instanced that is the actual Omega instance
#    is only created on actual attribute access
_om = OmegaDeferredInstance()
version = version  # ensure we keep imports
