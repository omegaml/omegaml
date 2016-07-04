import urlparse
import os
import sys
from util import load_class

OMEGA_TMP = '/tmp'
OMEGA_MONGO_URL = 'mongodb://localhost:27017/omega'
OMEGA_MONGO_COLLECTION = 'store'
OMEGA_BROKER = 'amqp://guest@127.0.0.1:5672//'
OMEGA_RESULT_BACKEND = OMEGA_MONGO_URL
OMEGA_NOTEBOOK_COLLECTION = 'ipynb'
parsed_url = urlparse.urlparse(OMEGA_RESULT_BACKEND)
OMEGA_CELERY_CONFIG = {
    'CELERY_ACCEPT_CONTENT': ['pickle', 'json', 'msgpack', 'yaml'],
    'CELERY_RESULT_BACKEND': OMEGA_RESULT_BACKEND,
    'CELERY_MONGODB_BACKEND_SETTINGS': {
        'database': parsed_url.path[1:],
        'taskmeta_collection': 'omegaml_taskmeta',
    }
}

OMEGA_BACKENDS = {
    'sklearn.joblib': load_class('omegaml.backends.ScikitLearnBackend')
}

# simple override from env vars
vars = locals()
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
    vars = { k : v for k,v in vars.iteritems() if k.startswith('OMEGA')}
    pprint(vars)
# -- test
if '-m unittest' in sys.argv:
    OMEGA_MONGO_URL = OMEGA_MONGO_URL.replace('/omega', '/test_omega')
