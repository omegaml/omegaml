from __future__ import absolute_import
import os
import sys
from .util import load_class, urlparse
import six
import yaml
from pprint import pprint

OMEGA_TMP = '/tmp'
OMEGA_MONGO_URL = (os.environ.get('OMEGA_MONGO_URL') or
                   os.environ.get('MONGO_URL') or
                   'mongodb://localhost:27017/omega')
OMEGA_MONGO_COLLECTION = 'omegaml'
OMEGA_BROKER = (os.environ.get('OMEGA_BROKER') or
                os.environ.get('RABBITMQ_URL') or
                'amqp://guest@127.0.0.1:5672//')
OMEGA_NOTEBOOK_COLLECTION = 'ipynb'
OMEGA_RESULT_BACKEND = 'amqp'

parsed_url = urlparse.urlparse(OMEGA_MONGO_URL)
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

OMEGA_BACKENDS = {
    'sklearn.joblib': load_class('omegaml.backends.ScikitLearnBackend'),
    'spark.mllib': load_class('omegaml.backends.SparkBackend')
}

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
