import multiprocessing
import os
from stackable.stackable import StackableSettings

concurrency = lambda: multiprocessing.cpu_count() * 2 + 1


class Config_Gunicorn(object):
    if 'PORT' in os.environ:
        bind = '0.0.0.0:{port}'.format(port=os.environ.get('PORT', 5000))
    else:
        bind = 'localhost:5000'
    timeout = os.environ.get('GUNICORN_TIMEOUT', 30)
    loglevel = 'debug'
    workers = os.environ.get('WEB_CONCURRENCY', concurrency())
    errorlog = '-'
    accesslog = '-'
    debug = True
    # allow at most 200 requests per worker before restarting
    max_requests = 100
    max_requests_jitter = 100
    graceful_timeout = 30

config = os.environ.get('GUNICORN_CONFIG', 'Config_Gunicorn')
StackableSettings.setup(globals(), locals()[config], use_lowercase=True)
