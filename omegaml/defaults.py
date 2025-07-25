from __future__ import absolute_import

from os.path import basename

import logging
import os
import shutil
import sys
from pathlib import Path

from omegaml.util import dict_merge, markup, inprogress, tryOr, mlflow_available

# determine how we're run
test_runners = {'test', 'nosetest', 'pytest', '_jb_unittest_runner.py'}
cmd_args = (basename(v) for v in sys.argv)
truefalse = lambda v: (v if isinstance(v, bool) else
                       any(str(v).lower().startswith(c) for c in ('y', 't', '1')))
is_cli_run = os.path.basename(sys.argv[0]) == 'om'
is_test_run = truefalse(os.environ.get('OMEGA_TEST_MODE'))
is_test_run |= len(set(test_runners) & set(cmd_args)) and 'omegaml-ce' in str(Path().cwd())

# enable unicode emoijs in stdout
tryOr(lambda: sys.stdout.reconfigure(encoding='utf-8'), None)

#: configuration file, by default will be searched in current directory, user config or site config
OMEGA_CONFIG_FILE = os.environ.get('OMEGA_CONFIG_FILE') or 'config.yml'
#: the temp directory used by omegaml processes
OMEGA_TMP = os.environ.get('OMEGA_TMP', '/tmp')
#: the fully qualified mongodb database URL, including the database name
OMEGA_MONGO_URL = (os.environ.get('OMEGA_MONGO_URL') or
                   os.environ.get('MONGO_URL') or
                   'mongodb://admin:foobar@localhost:27017/omega')
#: the collection name in the mongodb used by omegaml storage
OMEGA_MONGO_COLLECTION = 'omegaml'
#: bucket backwards compatibility
OMEGA_BUCKET_FS_LEGACY = False
#: determine if we should use SSL for mongodb and rabbitmq
OMEGA_USESSL = truefalse(os.environ.get('OMEGA_USESSL', False))
#: MongoClient ServerSelectionTimeoutMS
OMEGA_MONGO_TIMEOUT = int(os.environ.get('OMEGA_MONGO_TIMEOUT') or 2500)
#: additional kwargs for mongodb SSL connections
OMEGA_MONGO_SSL_KWARGS = {
    'tls': OMEGA_USESSL,
    'tlsCAFile': os.environ.get('CA_CERTS_PATH') or None,
    'uuidRepresentation': 'standard',
    'authSource': 'admin',
    # https://pymongo.readthedocs.io/en/4.8.0/migrate-to-pymongo4.html#directconnection-defaults-to-false
    'directConnection': True,
    'connectTimeoutMS': OMEGA_MONGO_TIMEOUT,  # since 4.10
    'serverSelectionTimeoutMS': OMEGA_MONGO_TIMEOUT,
}
#: if set forces eager execution of runtime tasks
OMEGA_LOCAL_RUNTIME = truefalse(os.environ.get('OMEGA_LOCAL_RUNTIME', False))
#: the celery broker name or URL
OMEGA_BROKER = (os.environ.get('OMEGA_BROKER') or
                os.environ.get('RABBITMQ_URL') or
                'amqp://admin:foobar@localhost:5672//')
#: is the worker considered inside the same cluster as the client
OMEGA_SERVICES_INCLUSTER = truefalse(os.environ.get('OMEGA_SERVICES_INCLUSTER', False))
#: (deprecated) the collection used to store ipython notebooks
OMEGA_NOTEBOOK_COLLECTION = 'ipynb'
#: the celery backend name or URL
OMEGA_RESULT_BACKEND = os.environ.get('OMEGA_RESULT_BACKEND', 'rpc://')
#: the omega worker label
OMEGA_WORKER_LABEL = os.environ.get('OMEGA_WORKER_LABEL') or os.environ.get('CELERY_Q', 'default')
#: the omega worker concurrency setting, defaults to 4
WORKER_CONCURRENCY = int(os.environ.get('OMEGA_WORKER_CONCURRENCY', 4))
WORKER_CONCURRENCY = WORKER_CONCURRENCY if WORKER_CONCURRENCY > 0 else os.cpu_count()

#: the celery configurations
OMEGA_CELERY_CONFIG = {
    # FIXME should work with json (the default celery serializer)
    'CELERY_ACCEPT_CONTENT': ['pickle', 'json'],
    'CELERY_TASK_SERIALIZER': 'pickle',
    'CELERY_RESULT_SERIALIZER': 'pickle',
    # according to docs, CELERY_RESULT_EXPIRES is the new setting
    # however as of 5.2.7 celery still refers CELERY_TASK_RESULT_EXPIRES
    # https://github.com/celery/celery/blob/7b585138af8318d62b8fe7086df7e85d110ac786/celery/app/defaults.py#L204
    'CELERY_RESULT_EXPIRES': 3600,  # expire results within 1 hour
    'CELERY_TASK_RESULT_EXPIRES': 3600,  # expire results within 1 hour
    'CELERY_DEFAULT_QUEUE': OMEGA_WORKER_LABEL,
    'BROKER_URL': OMEGA_BROKER,
    'BROKER_HEARTBEAT': 0,  # due to https://github.com/celery/celery/issues/4980
    # TODO replace result backend with redis or mongodb
    'CELERY_RESULT_BACKEND': OMEGA_RESULT_BACKEND,
    'CELERY_ALWAYS_EAGER': True if OMEGA_LOCAL_RUNTIME else False,
    'CELERYBEAT_SCHEDULE': {
        'execute_scripts': {
            'task': 'omegaml.notebook.tasks.execute_scripts',
            'schedule': 60,
        }
    },
    'BROKER_USE_SSL': OMEGA_USESSL,
    # keep behavior of retrying broker connections on startup
    'BROKER_CONNECTION_RETRY_ON_STARTUP': True,
    # limit concurrency
    'CELERYD_CONCURRENCY': WORKER_CONCURRENCY,
}
#: enable cloud worker routing
OMEGA_TASK_ROUTING_ENABLED = truefalse(os.environ.get('OMEGA_TASK_ROUTING_ENABLED', False))
#: celery task packages
OMEGA_CELERY_IMPORTS = ['omegaml',
                        'omegaml.notebook',
                        'omegaml.backends.package',
                        'omegaml.backends.monitoring']
#: REST API available objects
OMEGA_RESTAPI_FILTER = os.environ.get('OMEGA_RESTAPI_FILTER', '.*/.*/.*')
#: rest API URL, this is used by a client to connect to the server
OMEGA_RESTAPI_URL = os.environ.get('OMEGA_RESTAPI_URL', 'http://localhost:5000')
#: rest api uri, this is the relative path in OMEGA_RESTAPI_URL to the swagger.json
OMEGA_RESTAPI_SPECS_URI = '/api/doc/v1/swagger/specs/swagger.json'
#: hub url, this is used by the dashboard to display the hub's API endpoints in swagger UI (defaults to "current url")
OMEGA_HUB_URL = os.environ.get('OMEGA_HUB_URL', '') or None
#: storage backends
OMEGA_STORE_BACKENDS = {
    'experiment.tracker': 'omegaml.backends.tracking.ExperimentBackend',
    'sklearn.joblib': 'omegaml.backends.scikitlearn.ScikitLearnBackend',
    'ndarray.bin': 'omegaml.backends.npndarray.NumpyNDArrayBackend',
    'virtualobj.dill': 'omegaml.backends.virtualobj.VirtualObjectBackend',
    'pandas.rawdict': 'omegaml.backends.rawdict.PandasRawDictBackend',
    'python.file': 'omegaml.backends.rawfiles.PythonRawFileBackend',
    'python.package': 'omegaml.backends.package.PythonPackageData',
    'pipsrc.package': 'omegaml.backends.package.PythonPipSourcedPackageData',
    'pandas.csv': 'omegaml.backends.externaldata.PandasExternalData',
}
OMEGA_STORE_BACKENDS_TENSORFLOW = {
    'tfkeras.h5': 'omegaml.backends.tensorflow.TensorflowKerasBackend',
    'tfkeras.savedmodel': 'omegaml.backends.tensorflow.TensorflowKerasSavedModelBackend',
    'tf.savedmodel': 'omegaml.backends.tensorflow.TensorflowSavedModelBackend',
    'tfestimator.model': 'omegaml.backends.tensorflow.TFEstimatorModelBackend',
}
OMEGA_STORE_BACKENDS_KERAS = {
    'keras.h5': 'omegaml.backends.keras.KerasBackend',
}
OMEGA_STORE_BACKENDS_SQL = {
    'sqlalchemy.conx': 'omegaml.backends.sqlalchemy.SQLAlchemyBackend',
}
OMEGA_STORE_BACKENDS_MLFLOW = {
    'mlflow.model': 'omegaml.backends.mlflow.models.MLFlowModelBackend',
    'mlflow.project': 'omegaml.backends.mlflow.localprojects.MLFlowProjectBackend',
    'mlflow.gitproject': 'omegaml.backends.mlflow.gitprojects.MLFlowGitProjectBackend',
    'mlflow.registrymodel': 'omegaml.backends.mlflow.registrymodels.MLFlowRegistryBackend',
}
OMEGA_STORE_BACKENDS_R = {
    'model.r': 'omegaml.backends.rsystem.rmodels.RModelBackend',
    'package.r': 'omegaml.backends.rsystem.rscripts.RPackageData',
}
OMEGA_STORE_BACKENDS_OPENAI = {
    'genai.llm': 'omegaml.backends.genai.models.GenAIBaseBackend',
    'genai.text': 'omegaml.backends.genai.textmodel.TextModelBackend',
    'pgvector.conx': 'omegaml.backends.genai.pgvector.PGVectorBackend',
    'vector.conx': 'omegaml.backends.genai.mongovector.MongoDBVectorStore',
}
#: supported frameworks (deprecated since 0.16.2, it is effectively ignored)
OMEGA_FRAMEWORKS = os.environ.get('OMEGA_FRAMEWORKS', 'scikit-learn').split(',')
if is_test_run:
    OMEGA_FRAMEWORKS = ('scikit-learn', 'tensorflow', 'keras')
#: disable framework preloading, e.g. for web, jupyter
OMEGA_DISABLE_FRAMEWORKS = truefalse(os.environ.get('OMEGA_DISABLE_FRAMEWORKS'))
#: storage mixins
OMEGA_STORE_MIXINS = [
    'omegaml.mixins.store.ProjectedMixin',
    'omegaml.mixins.store.LazyGetMixin',
    'omegaml.mixins.store.virtualobj.VirtualObjectMixin',
    'omegaml.mixins.store.package.PythonPackageMixin',
    'omegaml.mixins.store.promotion.PromotionMixin',
    'omegaml.mixins.mdf.iotools.IOToolsStoreMixin',
    'omegaml.mixins.store.modelversion.ModelVersionMixin',
    'omegaml.mixins.store.datarevision.DataRevisionMixin',
    'omegaml.mixins.store.imexport.ObjectImportExportMixin',
    'omegaml.mixins.store.extdmeta.SignatureMixin',
    'omegaml.mixins.store.extdmeta.ScriptSignatureMixin',
    'omegaml.mixins.store.extdmeta.ModelSignatureMixin',
    'omegaml.mixins.store.requests.RequestCache',
    'omegaml.mixins.store.passthrough.PassthroughMixin',
    'omegaml.mixins.store.tracking.TrackableMetadataMixin',
    'omegaml.mixins.store.tracking.UntrackableMetadataMixin',
    'omegaml.mixins.store.objinfo.ObjectInformationMixin',
]
#: set hashed or clear names
OMEGA_STORE_HASHEDNAMES = truefalse(os.environ.get('OMEGA_STORE_HASHEDNAMES', True))
#: enable request caching for metadata
OMEGA_STORE_CACHE = truefalse(os.environ.get('OMEGA_STORE_CACHE', False))
#: runtimes mixins
OMEGA_RUNTIME_MIXINS = [
    'omegaml.runtimes.mixins.ModelMixin',
    'omegaml.runtimes.mixins.GridSearchMixin',
]
#: mdataframe mixins
OMEGA_MDF_MIXINS = [
    ('omegaml.mixins.mdf.ApplyMixin', 'MDataFrame,MSeries'),
    ('omegaml.mixins.mdf.FilterOpsMixin', 'MDataFrame,MSeries'),
    ('omegaml.mixins.mdf.apply.ApplyStatistics', 'MDataFrame,MSeries'),
    ('omegaml.mixins.mdf.applyutil.UtilitiesMixin', 'MDataFrame,MSeries'),
    ('omegaml.mixins.mdf.iotools.IOToolsMDFMixin', 'MDataFrame'),
    ('omegaml.mixins.mdf.ParallelApplyMixin', 'MDataFrame'),
]
#: mdataframe apply context mixins
OMEGA_MDF_APPLY_MIXINS = [
    ('omegaml.mixins.mdf.ApplyArithmetics', 'MDataFrame,MSeries'),
    ('omegaml.mixins.mdf.ApplyDateTime', 'MDataFrame,MSeries'),
    ('omegaml.mixins.mdf.ApplyString', 'MDataFrame,MSeries'),
    ('omegaml.mixins.mdf.ApplyAccumulators', 'MDataFrame,MSeries'),
]
#: jobs mixins
OMEGA_JOBPROXY_MIXINS = [
    'omegaml.runtimes.mixins.nbtasks.JobTasks',
]
#: user extensions
OMEGA_USER_EXTENSIONS = os.environ.get('OMEGA_USER_EXTENSIONS') or None
#: logging handler for om.logger
OMEGA_LOG_HANDLER = 'omegaml.store.logging.OmegaLoggingHandler'
#: route om.logger to python logger
OMEGA_LOG_PYTHON = False
#: log dataset
OMEGA_LOG_DATASET = '.omega/logs'
#: OmegaLoggingHandler log format
OMEGA_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
#: tracking providers
OMEGA_TRACKING_PROVIDERS = {
    'simple': 'omegaml.backends.tracking.OmegaSimpleTracker',
    'default': 'omegaml.backends.tracking.OmegaSimpleTracker',
    'profiling': 'omegaml.backends.tracking.OmegaProfilingTracker',
    'notrack': 'omegaml.backends.tracking.NoTrackTracker',
}
#: monitoring providers
OMEGA_MONITORING_PROVIDERS = {
    'models': 'omegaml.backends.monitoring.ModelDriftMonitor',
    'data': 'omegaml.backends.monitoring.DataDriftMonitor',
    'default': 'omegaml.backends.monitoring.DataDriftMonitor',
}
OMEGA_MONITORING_DRIFT_INTERVAL = 24 * 60 * 60  # 24 hours
OMEGA_MONITORING_MIXINS = {
    # 'DriftStatsCalc': ['omegaml.backends.monitoring.base.DriftStatsCalcMixin'],
}
#: session cache settings for cachetools.TTLCache
OMEGA_SESSION_CACHE = {
    'maxsize': 1,  # cache at most one session
    'ttl': 3600,  # keep it for 1 hour
}
#: allow overrides from local env upon retrieving config from hub (disable in workers)
OMEGA_ALLOW_ENV_CONFIG = truefalse(os.environ.get('OMEGA_ALLOW_ENV_CONFIG', '1'))
#: dashboard cards
OMEGA_CARDS_ENABLED = truefalse(os.environ.get('OMEGA_CARDS_ENABLED', False))


# =========================================
# ----- DO NOT MODIFY BELOW THIS LINE -----
# =========================================
# TODO move functions to util and make passing globals() explicit to avoid unintended side effects
def update_from_config(vars=globals(), config_file=OMEGA_CONFIG_FILE):
    """
    update omegaml.defaults from configuration file

    :param vars: the variables to update
    :param config_file: the path to config.yml or a file object
    :return:
    """
    # override from configuration file
    userconfig = markup(config_file, default={}, msg='could not read config file {}')
    if isinstance(userconfig, dict):
        for k in [k for k in userconfig.keys() if k.startswith('OMEGA')]:
            value = userconfig.get(k, None) or vars[k]
            if k in vars and isinstance(vars[k], dict):
                dict_merge(vars[k], value)
            else:
                vars[k] = value
    return vars


def update_from_env(vars=globals()):
    # simple override from env vars
    # -- only allow if enabled
    if not truefalse(vars.get('OMEGA_ALLOW_ENV_CONFIG', True)):
        return vars
    # -- top-level OMEGA_*
    for k in [k for k in os.environ.keys() if k.startswith('OMEGA')]:
        nv = os.environ.get(k, None) or vars.get(k)
        vars[k] = (truefalse(nv) if isinstance(vars.get(k), bool) else nv)
    # -- OMEGA_CELERY_CONFIG updates
    for k in [k for k in os.environ.keys() if k.startswith('OMEGA_CELERY')]:
        celery_k = k.replace('OMEGA_', '')
        vars['OMEGA_CELERY_CONFIG'][celery_k] = os.environ[k]
    # -- debug if required
    if '--print-omega-defaults' in sys.argv:
        from pprint import pprint
        vars = {k: v for k, v in vars.items() if k.startswith('OMEGA')}
        pprint(vars)
    return vars


def update_from_obj(obj, vars=globals(), attrs=None):
    """
    helper function to update omegaml.defaults from arbitrary module

    :param obj: the source object (must support getattr). Any
       upppe case variable/key in source is set in vars or attrs
    :param vars: the target object as a dict or obj
    :param attrs: the target object as attributes (deprecated). Specifying
        attrs takes precedence over vars and is equal to setting vars to attrs
    """

    def update(target, k, value):
        # for dict obj and dict value, merge the two, else set key or attribute
        if isinstance(value, dict):
            set_default(target, k, {})
            dict_merge(get_k(target, k), value)
        else:
            set_k(target, k, value)

    # helper functions that work for both dict and obj
    keys = lambda o: o.keys() if isinstance(o, dict) else dir(o)
    as_attrs = lambda o: not isinstance(o, dict)
    has_k = lambda o, k: hasattr(o, k) if as_attrs(o) else k in o
    get_k = lambda o, k: getattr(o, k) if as_attrs(o) else o[k]
    set_k = lambda o, k, v: setattr(o, k, v) if as_attrs(o) else o.__setitem__(k, v)
    set_default = lambda o, k, d: setattr(o, k, getattr(o, k, d) or d) if as_attrs(o) else o.__setitem__(k,
                                                                                                         o.get(k) or d)
    # update any
    target = attrs or vars
    for k in [k for k in keys(obj) if k.isupper()]:
        value = get_k(obj, k)
        update(target, k, value)


def update_from_dict(d, vars=globals(), attrs=None):
    """
    helper function to update omegaml.defaults from arbitrary dictionary

    :param d: the source dict (must support [] lookup). Any
       uppercase variable is set in omegaml.defaults
    """
    return update_from_obj(d, vars=vars, attrs=attrs)


def locate_config_file(configfile=OMEGA_CONFIG_FILE):
    """
    locate the configuration file, if any

    Will search the following locations for the config file:
        1. current directory and all paths up to root
        2. user configuration directory
        3. site configuration directory

    The exact location depends on the platform:
        Linux:
            user = ~/.config/omegaml
            site = /etc/xdg/omegaml
        Windows:
            user = C:\\Documents and Settings\\<User>\\Application Data\\omegaml\\omegaml
            site = C:\\Documents and Settings\\All Users\\Application Data\\omegaml\\omegaml
        Mac:
            user = ~/Library/Application Support/omegaml
            site = /Library/Application Support/omegaml

    See the appdirs package for details on the platform specific locations of the
    user and site config dir, https://pypi.org/project/appdirs/

    Args:
        configfile: the default config file name or path

    Returns:
        location of the config file or None if not found
    """
    try:
        from appdirs import user_config_dir, site_config_dir
    except:
        # we don't have appdirs installed, this can happen during setup.py. fake it
        user_config_dir = lambda *args: os.path.expanduser('~/.config/omegaml')
        site_config_dir = lambda *args: '/etc/xdg/omegaml'

    if os.path.exists(configfile):
        return os.path.abspath(configfile)
    appdirs_args = ('omegaml', 'omegaml')
    cur_dir_tree = lambda *args: Path(os.getcwd()).parents
    all_dirs = (cur_dir_tree(), [user_config_dir(*appdirs_args)], [site_config_dir(*appdirs_args)])
    flatten = lambda l: (item for sl in l for item in sl)
    for cfgdir in flatten(all_dirs):
        cfgfile = os.path.join(cfgdir, os.path.basename(configfile))
        if os.path.exists(cfgfile):
            return cfgfile
    return None


@inprogress(text="loading extensions...")
def load_user_extensions(vars=globals()):
    """
    user extensions are extensions to settings

    Usage:
        in config.yml specify, e.g.

            OMEGA_USER_EXTENSIONS:
                OMEGA_STORE_BACKENDS:
                   KIND: path.to.BackendClass
                EXTENSION_LOADER: path.to.module

        This will extend OMEGA_STORE_BACKENDS and load path.to.module. If the
        EXENSION_LOADER given module has a run(vars) method, it will be called
        using the current defaults variables (dict) as input.

    Args:
        extensions (dict): a list of extensions in the form python.path.to.module or
             <setting_name>: <value>

    Returns:
        None
    """
    extensions = vars.get('OMEGA_USER_EXTENSIONS') or {}
    if not isinstance(extensions, dict):
        extensions = markup(extensions, default={})
    for k, v in extensions.items():
        omvar = vars.get(k)
        try:
            if isinstance(omvar, list):
                omvar.append(v)
            elif isinstance(omvar, dict):
                omvar.update(v)
            elif k == 'EXTENSION_LOADER':
                from importlib import import_module
                mod = import_module(v)
                if hasattr(mod, 'run'):
                    mod.run(vars)
            else:
                raise ValueError
        except:
            omvar_type = type(omvar)
            k_type = type(v)
            msg = ('user extensions error: cannot apply {k} to {omvar}, '
                   'expected type {omvar_type} got {k_type}').format(**locals())
            raise ValueError(msg)


@inprogress(text='loading frameworks...')
def load_framework_support(vars=globals()):
    # load framework-specific backends
    # -- note we do this here to ensure this happens after config updates
    from omegaml.util import tensorflow_available, keras_available, module_available

    if OMEGA_DISABLE_FRAMEWORKS:
        return
    if tensorflow_available():
        #: tensorflow backend
        # https://stackoverflow.com/a/38645250
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = os.environ.get('TF_CPP_MIN_LOG_LEVEL') or '3'
        logging.getLogger('tensorflow').setLevel(logging.ERROR)
        vars['OMEGA_STORE_BACKENDS'].update(vars['OMEGA_STORE_BACKENDS_TENSORFLOW'])
    #: openapi backend
    if module_available('openai'):
        vars['OMEGA_STORE_BACKENDS'].update(vars['OMEGA_STORE_BACKENDS_OPENAI'])
    #: keras backend
    if keras_available():
        vars['OMEGA_STORE_BACKENDS'].update(vars['OMEGA_STORE_BACKENDS_KERAS'])
    #: sqlalchemy backend
    if module_available('sqlalchemy'):
        vars['OMEGA_STORE_BACKENDS'].update(vars['OMEGA_STORE_BACKENDS_SQL'])
    #: r environment
    if shutil.which('R') is not None:
        vars['OMEGA_STORE_BACKENDS'].update(vars['OMEGA_STORE_BACKENDS_R'])
    #: mlflow backends
    if mlflow_available():
        vars['OMEGA_STORE_BACKENDS'].update(vars['OMEGA_STORE_BACKENDS_MLFLOW'])


@inprogress(text='loading configuration...')
def load_config_file(vars=globals(), config_file=OMEGA_CONFIG_FILE):
    config_file = locate_config_file(config_file)
    vars['OMEGA_CONFIG_FILE'] = config_file
    update_from_config(vars, config_file=config_file)
    if is_cli_run:
        import warnings
        warnings.filterwarnings("ignore", category=FutureWarning)


# -- test support
if not is_cli_run and is_test_run:
    # this is to avoid using production settings during test
    OMEGA_MONGO_URL = OMEGA_MONGO_URL.replace('/omega', '/testdb')
    OMEGA_LOCAL_RUNTIME = True
    OMEGA_RESTAPI_URL = 'local'
    logging.getLogger().setLevel(logging.ERROR)
else:
    # overrides in actual operations
    load_config_file()

# load extensions, always last step to ensure we have user configs loaded
update_from_env()
