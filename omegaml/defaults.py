from __future__ import absolute_import

import logging
import os
import sys
from os.path import basename

import six
import yaml

from omegaml.util import tensorflow_available, keras_available

user_homedir = os.path.expanduser('~')

#: configuration file, defaults to $HOME/.omegaml/config.yml
OMEGA_CONFIG_FILE = os.path.join(user_homedir, '.omegaml', 'config.yml')
#: the temp directory used by omegaml processes
OMEGA_TMP = '/tmp'
#: the fully qualified mongodb database URL, including the database name
OMEGA_MONGO_URL = (os.environ.get('OMEGA_MONGO_URL') or
                   os.environ.get('MONGO_URL') or
                   'mongodb://admin:foobar@localhost:27017/omega')
#: the collection name in the mongodb used by omegaml storage
OMEGA_MONGO_COLLECTION = 'omegaml'
#: if set forces eager execution of runtime tasks
OMEGA_LOCAL_RUNTIME = os.environ.get('OMEGA_LOCAL_RUNTIME')
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
    'BROKER_URL': OMEGA_BROKER,
    'CELERY_RESULT_BACKEND': OMEGA_RESULT_BACKEND,
    'CELERY_ALWAYS_EAGER': True if OMEGA_LOCAL_RUNTIME else False,
    'CELERYBEAT_SCHEDULE': {
        'execute_scripts': {
            'task': 'omegaml.notebook.tasks.execute_scripts',
            'schedule': 60,
        },
    },
}
#: celery task packages
OMEGA_CELERY_IMPORTS = ['omegaml.tasks', 'omegaml.notebook.tasks']
#: storage backends
OMEGA_STORE_BACKENDS = {
    'sklearn.joblib': 'omegaml.backends.ScikitLearnBackend',
    'ndarray.bin': 'omegaml.backends.npndarray.NumpyNDArrayBackend',
    'virtualobj.dill': 'omegaml.backends.virtualobj.VirtualObjectBackend',
    'pandas.rawdict': 'omegaml.backends.rawdict.PandasRawDictBackend',
    'python.file': 'omegaml.backends.rawfiles.PythonRawFileBackend',
}

#: tensorflow backend
# https://stackoverflow.com/a/38645250
os.environ['TF_CPP_MIN_LOG_LEVEL'] = os.environ.get('TF_CPP_MIN_LOG_LEVEL') or '3'
logging.getLogger('tensorflow').setLevel(logging.ERROR)
if tensorflow_available():
    OMEGA_STORE_BACKENDS.update({
        'tfkeras.h5': 'omegaml.backends.tensorflow.TensorflowKerasBackend',
        'tfkeras.savedmodel': 'omegaml.backends.tensorflow.TensorflowKerasSavedModelBackend',
        'tf.savedmodel': 'omegaml.backends.tensorflow.TensorflowSavedModelBackend',
        'tfestimator.model': 'omegaml.backends.tensorflow.TFEstimatorModelBackend',
    })
#: keras backend
if keras_available():
    OMEGA_STORE_BACKENDS.update({
        'keras.h5': 'omegaml.backends.keras.KerasBackend',
    })

#: storage mixins
OMEGA_STORE_MIXINS = [
    'omegaml.mixins.store.ProjectedMixin',
    'omegaml.mixins.store.virtualobj.VirtualObjectMixin',
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
    else:
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

# -- test
if any(m in [basename(arg) for arg in sys.argv]
       for m in ('unittest', 'test', 'nosetests', 'noserunner', '_jb_unittest_runner.py',
                 '_jb_nosetest_runner.py')):
    OMEGA_MONGO_URL = OMEGA_MONGO_URL.replace('/omega', '/testdb')
    OMEGA_CELERY_CONFIG['CELERY_ALWAYS_EAGER'] = True
    OMEGA_RESTAPI_URL = ''
    logging.getLogger().setLevel(logging.ERROR)
else:
    # overrides in actual operations
    # this is to avoid using production settings during test
    update_from_config(globals())
    update_from_env(globals())
