from __future__ import absolute_import

from os.path import basename

import logging
import os
import six
import sys
import yaml

from omegaml.util import tensorflow_available, keras_available, module_available

# determine how we're run
is_cli_run = os.path.basename(sys.argv[0]) == 'om'
is_test_run = any(m in [basename(arg) for arg in sys.argv]
                  for m in ('unittest', 'test', 'nosetests', 'noserunner', '_jb_unittest_runner.py',
                            '_jb_nosetest_runner.py'))

#: configuration file, by default will be searched in current directory, user config or site config
OMEGA_CONFIG_FILE = os.environ.get('OMEGA_CONFIG_FILE') or 'config.yml'
#: the temp directory used by omegaml processes
OMEGA_TMP = '/tmp'
#: the fully qualified mongodb database URL, including the database name
OMEGA_MONGO_URL = (os.environ.get('OMEGA_MONGO_URL') or
                   os.environ.get('MONGO_URL') or
                   'mongodb://admin:foobar@localhost:27017/omega')
#: the collection name in the mongodb used by omegaml storage
OMEGA_MONGO_COLLECTION = 'omegaml'
#: determine if we should use SSL for mongodb and rabbitmq
OMEGA_USESSL = True if os.environ.get('OMEGA_USESSL') else False
#: additional kwargs for mongodb SSL connections
OMEGA_MONGO_SSL_KWARGS = {
    'ssl': OMEGA_USESSL,
}
#: if set forces eager execution of runtime tasks
OMEGA_LOCAL_RUNTIME = os.environ.get('OMEGA_LOCAL_RUNTIME', False)
#: the celery broker name or URL
OMEGA_BROKER = (os.environ.get('OMEGA_BROKER') or
                os.environ.get('RABBITMQ_URL') or
                'amqp://guest@127.0.0.1:5672//')
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
    'CELERY_DEFAULT_QUEUE': os.environ.get('CELERY_Q', 'default'),
    'BROKER_URL': OMEGA_BROKER,
    'BROKER_HEARTBEAT': 0,  # due to https://github.com/celery/celery/issues/4980
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
    'sklearn.joblib': 'omegaml.backends.ScikitLearnBackend',
    'ndarray.bin': 'omegaml.backends.npndarray.NumpyNDArrayBackend',
    'virtualobj.dill': 'omegaml.backends.virtualobj.VirtualObjectBackend',
    'pandas.rawdict': 'omegaml.backends.rawdict.PandasRawDictBackend',
    'python.file': 'omegaml.backends.rawfiles.PythonRawFileBackend',
    'python.package': 'omegaml.backends.package.PythonPackageData',
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
#: supported frameworks
if is_test_run:
    OMEGA_FRAMEWORKS = ('scikit-learn', 'tensorflow', 'keras')
else:
    OMEGA_FRAMEWORKS = os.environ.get('OMEGA_FRAMEWORKS') or ('scikit-learn')

#: storage mixins
OMEGA_STORE_MIXINS = [
    'omegaml.mixins.store.ProjectedMixin',
    'omegaml.mixins.store.virtualobj.VirtualObjectMixin',
    'omegaml.mixins.store.package.PythonPackageMixin',
    'omegaml.mixins.store.promotion.PromotionMixin',
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
]
#: mdataframe apply context mixins
OMEGA_MDF_APPLY_MIXINS = [
    ('omegaml.mixins.mdf.ApplyArithmetics', 'MDataFrame,MSeries'),
    ('omegaml.mixins.mdf.ApplyDateTime', 'MDataFrame,MSeries'),
    ('omegaml.mixins.mdf.ApplyString', 'MDataFrame,MSeries'),
    ('omegaml.mixins.mdf.ApplyAccumulators', 'MDataFrame,MSeries'),
]
#: user extensions
OMEGA_USER_EXTENSIONS = os.environ.get('OMEGA_USER_EXTENSIONS') or None
#: log dataset
OMEGA_LOG_DATASET = '.omega/logs'
#: OmegaLoggingHandler log format
OMEGA_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# =========================================
# ----- DO NOT MODIFY BELOW THIS LINE -----
# =========================================
def update_from_config(vars=globals(), config_file=OMEGA_CONFIG_FILE):
    """
    update omegaml.defaults from configuration file

    :param vars: the variables to update
    :param config_file: the path to config.yml or a file object
    :return:
    """
    # override from configuration file
    userconfig = {}
    if isinstance(config_file, six.string_types):
        if os.path.exists(config_file):
            with open(config_file, 'r') as fin:
                userconfig = yaml.safe_load(fin)
    elif hasattr(config_file, 'read'):
        userconfig = yaml.safe_load(config_file)
    if userconfig:
        for k in [k for k in vars.keys() if k.startswith('OMEGA')]:
            value = userconfig.get(k, None) or vars[k]
            if isinstance(vars[k], dict):
                vars[k].update(value)
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
       variable starting with OMEGA is set in omegaml.defaults
    """
    for k in [k for k in dir(obj) if k.startswith('OMEGA')]:
        if hasattr(obj, k):
            value = getattr(obj, k)
            if attrs:
                setattr(attrs, k, value)
            else:
                vars[k] = value


def update_from_dict(d, vars=globals(), attrs=None):
    """
    helper function to update omegaml.defaults from arbitrary dictionary

    :param d: the source dict (must support [] lookup). Any
       variable starting with OMEGA is set in omegaml.defaults
    """
    for k, v in six.iteritems(d):
        if k.startswith('OMEGA'):
            if attrs:
                setattr(attrs, k, v)
            else:
                vars[k] = v


# load Enterprise Edition if available
try:
    from omegaee import eedefaults

    update_from_obj(eedefaults, vars=globals())
except Exception as e:
    pass


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


def load_user_extensions(extensions=OMEGA_USER_EXTENSIONS, vars=globals()):
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


# -- test
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

# load framework-specific backends
# -- note we do this here to ensure this happens after config updates
if 'tensorflow' in OMEGA_FRAMEWORKS and tensorflow_available():
    #: tensorflow backend
    # https://stackoverflow.com/a/38645250
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = os.environ.get('TF_CPP_MIN_LOG_LEVEL') or '3'
    logging.getLogger('tensorflow').setLevel(logging.ERROR)
    OMEGA_STORE_BACKENDS.update(OMEGA_STORE_BACKENDS_TENSORFLOW)
#: keras backend
if 'keras' in OMEGA_FRAMEWORKS and keras_available():
    OMEGA_STORE_BACKENDS.update(OMEGA_STORE_BACKENDS_KERAS)
#: sqlalchemy backend
if module_available('sqlalchemy'):
    OMEGA_STORE_BACKENDS.update(OMEGA_STORE_BACKENDS_SQL)

# load user extensions if any
if OMEGA_USER_EXTENSIONS is not None:
    load_user_extensions(OMEGA_USER_EXTENSIONS)
