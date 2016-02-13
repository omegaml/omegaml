OMEGA_TMP = '/tmp'
OMEGA_MONGO_URL = 'mongodb://localhost:27017/omega'
OMEGA_MONGO_COLLECTION = 'store'
OMEGA_BROKER = 'amqp://guest@localhost//'
OMEGA_RESULTS_BACKEND = 'amqp://'
OMEGA_CELERY_CONFIG = {
    'CELERY_ACCEPT_CONTENT': ['pickle', 'json', 'msgpack', 'yaml'],
    'CELERY_RESULT_BACKEND': OMEGA_RESULTS_BACKEND,
}

# simple override from env vars
import os
import sys
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
