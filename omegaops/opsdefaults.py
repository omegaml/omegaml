from os.path import basename

import os
import sys
from omegaml import _base_config as omdefaults

OMEGA_BROKER = (os.environ.get('OMEGA_BROKER') or
                os.environ.get('RABBITMQ_URL') or
                'amqp://guest@localhost:5672//')

#: the celery backend name or URL
OMEGA_RESULT_BACKEND = 'amqp'
OMEGA_LOCAL_RUNTIME = os.environ.get('OMEGA_LOCAL_RUNTIME', False)

#: deployment scheduler rate. adjust to worker load
DEPLOY_SCHEDULE_RATE = int(os.environ.get('OMEGA_DEPLOY_SCHEDULE_RATE', 15))
#: user scheduler rate. adjust to worker load
USER_SCHEDULER_RATE = int(os.environ.get('OMEGA_USER_SCHEDULER_RATE', 15 * 60))
#: task time limit
TASK_TIME_LIMIT = int(os.environ.get('OMEGA_TASK_TIMELIMIT', 30 * 60))

OMEGA_CELERY_CONFIG = {
    'CELERYBEAT_SCHEDULE': {
        'paas_execute_pending': {
            'task': 'paasdeploy.tasks.execute_pending',
            'schedule': DEPLOY_SCHEDULE_RATE,
            'options': {
                'queue': 'omegaops',
            }
        },
        'run_user_scheduler': {
            'task': 'omegaops.tasks.run_user_scheduler',
            'schedule': USER_SCHEDULER_RATE,
            'options': {
                'queue': 'omegaops',
            }
        },
        'ensure_user_broker_ready': {
            'task': 'omegaops.tasks.ensure_user_broker_ready',
            'schedule': USER_SCHEDULER_RATE,
            'options': {
                'queue': 'omegaops',
            }
        }
    },
    # avoid indefinite waits on task publishing if broker is down
    # -- without this we had indef waits in run_user_scheduler
    # -- see https://github.com/celery/celery/issues/4627
    'BROKER_TRANSPORT_OPTIONS': {
        "max_retries": 3,
        "interval_start": 0,
        "interval_step": 1,
        "interval_max": 5,
    },
    # limit worker prefetch to one, increasing resilience in case of worker
    # issues
    'CELERYD_PREFETCH_MULTIPLIER': 1,
    # avoid tasks run forever
    'CELERYD_TIME_LIMIT': TASK_TIME_LIMIT,
    # allow custom logging configuration
    'CELERYD_HIJACK_ROOT_LOGGER': False,
}
#: celery task packages
OMEGA_CELERY_IMPORTS = ['paasdeploy', 'omegaops']
OMEGA_CELERY_IMPORTS += omdefaults.OMEGA_CELERY_IMPORTS

# remove omdefaults schedule entry
del omdefaults.OMEGA_CELERY_CONFIG['CELERYBEAT_SCHEDULE']

# test support -- always run tasks locally
if any(m in [basename(arg) for arg in sys.argv]
       # this is to avoid using production settings during test
       for m in ('unittest', 'test', 'nosetests', 'noserunner', '_jb_unittest_runner.py',
                 '_jb_nosetest_runner.py')):
    OMEGA_LOCAL_RUNTIME = True

# allow overloading settings from EnvSettings
from stackable import StackableSettings
StackableSettings.load(globals())
