from __future__ import absolute_import
import os
import sys
from .util import load_class
import six
import yaml

#: the temp directory used by omegaml processes
OMEGA_TMP = '/tmp'
#: the fully qualified mongodb database URL, including the database name
OMEGA_MONGO_URL = (os.environ.get('OMEGA_MONGO_URL') or
                   os.environ.get('MONGO_URL') or
                   'mongodb://localhost:27017/omega')
#: the collection name in the mongodb used by omegaml storage
OMEGA_MONGO_COLLECTION = 'omegaml'
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
    'CELERY_ACCEPT_CONTENT': ['pickle', 'json', 'msgpack', 'yaml'],
    'BROKER_URL': OMEGA_BROKER,
    'CELERY_RESULT_BACKEND': OMEGA_RESULT_BACKEND,
    'CELERYBEAT_SCHEDULE': {
        'execute_scripts': {
            'task': 'omegaml.tasks.execute_scripts',
            'schedule': 60,
        },
    },
}
#: storage backends
OMEGA_STORE_BACKENDS = {
    'sklearn.joblib': load_class('omegaml.backends.ScikitLearnBackend'),
    'spark.mllib': load_class('omegaml.backends.SparkBackend'),
    'pandas.csv': load_class('omegaml.backends.PandasExternalData')
}
#: storage mixins
OMEGA_STORE_MIXINS = [
    load_class('omegaml.backends.mixins.ProjectedMixin'),
]
#: runtime mixins
OMEGA_RUNTIME_MIXINS = [
    load_class('omegaml.runtime.mixins.ModelMixin'),
]

#: the omegaweb url
OMEGA_RESTAPI_URL = (os.environ.get('OMEGA_RESTAPI_URL') or
                     'http://omegaml.dokku.me/')
#: omega user id
OMEGA_USERID = None
#: omega apikey
OMEGA_APIKEY = None


def update_from_config(vars=vars):
    # override from configuration file
    if os.path.exists(config_file):
        with open(config_file, 'r') as fin:
            userconfig = yaml.load(fin)
        if userconfig:
            for k in [k for k in vars.keys() if k.startswith('OMEGA')]:
                vars[k] = userconfig.get(k, None) or vars[k]


def update_from_env(vars=vars):
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


def update_from_obj(obj):
    """
    helper function to update omegaml.defaults from arbitrary module

    :param obj: the source object (must support getattr). Any
       variable starting with OMEGA is set in omegaml.defaults, provided
       it exists there already. 
    """
    for k in [k for k in globals() if k.startswith('OMEGA')]:
        if hasattr(obj, k):
            value = getattr(obj, k)
            setattr(obj, k, value)

# -- test
if any(m in sys.argv for m in ('unittest', 'test')):
    OMEGA_MONGO_URL = OMEGA_MONGO_URL.replace('/omega', '/testdb')
    OMEGA_CELERY_CONFIG['CELERY_ALWAYS_EAGER'] = True
    OMEGA_RESTAPI_URL = ''
else:
    # overrides in actual operations
    # this is to avoid using production settings during test
    user_homedir = os.path.expanduser('~')
    config_file = os.path.join(user_homedir, '.omegaml', 'config.yml')
    update_from_config(globals())
    update_from_env(globals())
