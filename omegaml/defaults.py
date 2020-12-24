from __future__ import absolute_import

from os.path import basename

import logging
import os
import six
import sys

from omegaml.util import tensorflow_available, keras_available, module_available, markup, dict_merge

# determine how we're run
is_cli_run = os.path.basename(sys.argv[0]) == 'om'
is_test_run = any(m in [basename(arg) for arg in ' '.join(sys.argv).split(' ')]
                  for m in ('unittest', 'test', 'nosetests', 'noserunner', '_jb_unittest_runner.py',
                            '_jb_nosetest_runner.py')) or os.environ.get('OMEGA_TEST_MODE')

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
OMEGA_USESSL = True if os.environ.get('OMEGA_USESSL') else False
#: additional kwargs for mongodb SSL connections
OMEGA_MONGO_SSL_KWARGS = {
    'ssl': OMEGA_USESSL,
    'tlsCAFile': os.environ.get('CA_CERTS_PATH') or None,
}
#: if set forces eager execution of runtime tasks
OMEGA_LOCAL_RUNTIME = os.environ.get('OMEGA_LOCAL_RUNTIME', False)
#: the celery broker name or URL
OMEGA_BROKER = (os.environ.get('OMEGA_BROKER') or
                os.environ.get('RABBITMQ_URL') or
                'amqp://admin:foobar@localhost:5672//')
#: is the worker considered inside the same cluster as the client
OMEGA_WORKER_INCLUSTER = False
#: (deprecated) the collection used to store ipython notebooks
OMEGA_NOTEBOOK_COLLECTION = 'ipynb'
#: the celery backend name or URL
OMEGA_RESULT_BACKEND = 'amqp'
#: the celery configurations
OMEGA_CELERY_CONFIG = {
    # FIXME should work with json (the default celery serializer)
    'CELERY_ACCEPT_CONTENT': ['pickle', 'json'],
    'CELERY_TASK_SERIALIZER': 'pickle',
    'CELERY_RESULT_SERIALIZER': 'pickle',
    'CELERY_TASK_RESULT_EXPIRES': 3600,  # expire results within 1 hour
    'CELERY_DEFAULT_QUEUE': os.environ.get('CELERY_Q', 'default'),
    'BROKER_URL': OMEGA_BROKER,
    'BROKER_HEARTBEAT': 0,  # due to https://github.com/celery/celery/issues/4980
    # TODO replace result backend with redis or mongodb
    'CELERY_RESULT_BACKEND': OMEGA_RESULT_BACKEND,
    'CELERY_ALWAYS_EAGER': True if OMEGA_LOCAL_RUNTIME else False,
    'CELERYBEAT_SCHEDULE': {
        'execute_scripts': {
            'task': 'omegaml.notebook.tasks.execute_scripts',
            'schedule': 60,
        },
    },
    'BROKER_USE_SSL': OMEGA_USESSL,
}
#: enable cloud worker routing
OMEGA_TASK_ROUTING_ENABLED = os.environ.get('OMEGA_TASK_ROUTING_ENABLED', False)
#: celery task packages
OMEGA_CELERY_IMPORTS = ['omegaml',
                        'omegaml.notebook',
                        'omegaml.backends.package']
#: storage backends
OMEGA_STORE_BACKENDS = {
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
OMEGA_STORE_BACKENDS_DASH = {
    'python.dash': 'omegaml.backends.dashapp.DashAppBackend',
}
OMEGA_STORE_BACKENDS_SQL = {
    'sqlalchemy.conx': 'omegaml.backends.sqlalchemy.SQLAlchemyBackend',
}
#: supported frameworks
OMEGA_FRAMEWORKS = os.environ.get('OMEGA_FRAMEWORKS', 'scikit-learn').split(',')
if is_test_run:
    OMEGA_FRAMEWORKS = ('scikit-learn', 'tensorflow', 'keras', 'dash')
#: disable framework preloading, e.g. for web, jupyter
OMEGA_DISABLE_FRAMEWORKS = os.environ.get('OMEGA_DISABLE_FRAMEWORKS')
#: storage mixins
OMEGA_STORE_MIXINS = [
    'omegaml.mixins.store.ProjectedMixin',
    'omegaml.mixins.store.LazyGetMixin',
    'omegaml.mixins.store.virtualobj.VirtualObjectMixin',
    'omegaml.mixins.store.package.PythonPackageMixin',
    'omegaml.mixins.store.promotion.PromotionMixin',
    'omegaml.mixins.mdf.iotools.IOToolsStoreMixin',
    'omegaml.mixins.store.modelversion.ModelVersionMixin',
]
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
#: log dataset
OMEGA_LOG_DATASET = '.omega/logs'
#: OmegaLoggingHandler log format
OMEGA_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
#: MongoClient ServerSelectionTimeoutMS
OMEGA_MONGO_TIMEOUT = int(os.environ.get('OMEGA_MONGO_TIMEOUT') or 2500)


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
        for k in [k for k in vars.keys() if k.startswith('OMEGA')]:
            value = userconfig.get(k, None) or vars[k]
            if isinstance(vars[k], dict):
                dict_merge(vars[k], value)
            else:
                vars[k] = value
    return vars


def update_from_env(vars=globals()):
    # simple override from env vars
    # -- top-level OMEGA_*
    for k in [k for k in vars.keys() if k.startswith('OMEGA')]:
        vars[k] = os.environ.get(k, None) or vars[k]
    # -- OMEGA_CELERY_CONFIG updates
    for k in [k for k in os.environ.keys() if k.startswith('OMEGA_CELERY')]:
        celery_k = k.replace('OMEGA_', '')
        vars['OMEGA_CELERY_CONFIG'][celery_k] = os.environ[k]
    # -- debug if required
    if '--print-omega-defaults' in sys.argv:
        from pprint import pprint
        vars = {k: v for k, v in six.iteritems(vars) if k.startswith('OMEGA')}
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
        1. current directory
        2. user configuration directory
        3. site configuration directory

    The exact location depends on the platform:
        Linux:
            user = ~/.config/omegaml
            site = /etc/xdg/omegaml
        Windows:
            user = C:\Documents and Settings\<User>\Application Data\omegaml\omegaml
            site = C:\Documents and Settings\All Users\Application Data\omegaml\omegaml
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
        return configfile
    appdirs_args = ('omegaml', 'omegaml')
    for cfgdir in (os.getcwd(), user_config_dir(*appdirs_args), site_config_dir(*appdirs_args)):
        cfgfile = os.path.join(cfgdir, os.path.basename(configfile))
        if os.path.exists(cfgfile):
            return cfgfile
    return None


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


def load_framework_support(vars=globals()):
    # load framework-specific backends
    # -- note we do this here to ensure this happens after config updates
    if OMEGA_DISABLE_FRAMEWORKS:
        return
    if 'tensorflow' in vars['OMEGA_FRAMEWORKS'] and tensorflow_available():
        #: tensorflow backend
        # https://stackoverflow.com/a/38645250
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = os.environ.get('TF_CPP_MIN_LOG_LEVEL') or '3'
        logging.getLogger('tensorflow').setLevel(logging.ERROR)
        vars['OMEGA_STORE_BACKENDS'].update(vars['OMEGA_STORE_BACKENDS_TENSORFLOW'])
    #: keras backend
    if 'keras' in vars['OMEGA_FRAMEWORKS'] and keras_available():
        vars['OMEGA_STORE_BACKENDS'].update(vars['OMEGA_STORE_BACKENDS_KERAS'])
    #: sqlalchemy backend
    if module_available('sqlalchemy'):
        vars['OMEGA_STORE_BACKENDS'].update(vars['OMEGA_STORE_BACKENDS_SQL'])
    #: dash backend
    if 'dash' in OMEGA_FRAMEWORKS and module_available('dashserve'):
        vars['OMEGA_STORE_BACKENDS'].update(vars['OMEGA_STORE_BACKENDS_DASH'])


# -- test support
# this is to avoid using production settings during test
if not is_cli_run and is_test_run:
    OMEGA_MONGO_URL = OMEGA_MONGO_URL.replace('/omega', '/testdb')
    OMEGA_LOCAL_RUNTIME = True
    OMEGA_RESTAPI_URL = ''
    logging.getLogger().setLevel(logging.ERROR)
else:
    # overrides in actual operations
    OMEGA_CONFIG_FILE = locate_config_file()
    update_from_config(globals(), config_file=OMEGA_CONFIG_FILE)
    update_from_env(globals())
    if is_cli_run:
        # be les
        import warnings

        warnings.filterwarnings("ignore", category=FutureWarning)

# load extensions, always last step to ensure we have user configs loaded
load_framework_support()
load_user_extensions()
