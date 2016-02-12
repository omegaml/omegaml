OMEGA_TMP = '/tmp'
OMEGA_MONGO_URL = 'mongodb://localhost:27017/omega'
OMEGA_MONGO_COLLECTION = 'store'
OMEGA_BROKER = 'amqp://guest@localhost//'
OMEGA_RESULTS_BACKEND = 'amqp://'
OMEGA_CELERY_CONFIG = {
    'CELERY_ACCEPT_CONTENT': ['pickle', 'json', 'msgpack', 'yaml'],
    'CELERY_RESULT_BACKEND': OMEGA_RESULTS_BACKEND,
}
