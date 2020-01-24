import os

import sys
from os.path import basename

OMEGA_BROKER = (os.environ.get('OMEGA_BROKER') or
                os.environ.get('RABBITMQ_URL') or
                'amqp://guest@127.0.0.1:5672//')

#: the celery backend name or URL
OMEGA_RESULT_BACKEND = 'amqp'
OMEGA_LOCAL_RUNTIME = os.environ.get('OMEGA_LOCAL_RUNTIME', False)

#: deployment scheduler rate. adjust to worker load
DEPLOY_SCHEDULE_RATE=int(os.environ.get('OMEGA_DEPLOY_SCHEDULE_RATE', 10))
#: user scheduler rate. adjust to worker load
USER_SCHEDULER_RATE=int(os.environ.get('OMEGA_USER_SCHEDULER_RATE', 120))

OMEGA_CLOUD_CELERY_CONFIG = {
    'CELERY_ACCEPT_CONTENT': ['pickle', 'json', 'msgpack', 'yaml'],
    'BROKER_URL': OMEGA_BROKER,
    'CELERY_RESULT_BACKEND': OMEGA_RESULT_BACKEND,
    'CELERY_ALWAYS_EAGER': True if OMEGA_LOCAL_RUNTIME else False,
    'CELERYBEAT_SCHEDULE': {
        'deploy_pending_services': {
            'task': 'paasdeploy.tasks.deploy_pending_services',
            'schedule': DEPLOY_SCHEDULE_RATE,
            'options': {
                'queue': 'omegaops',
            }
        },
        'execute_pending_commands': {
            'task': 'paasdeploy.tasks.execute_pending_commands',
            'schedule': DEPLOY_SCHEDULE_RATE,
            'options': {
                'queue': 'omegaops',
            }
        },
        'execute_pending_tasks': {
            'task': 'paasdeploy.tasks.execute_pending_tasks',
            'schedule': DEPLOY_SCHEDULE_RATE,
            'options': {
                'queue': 'omegaops',
            }
        },
        'update_deployment_status': {
            'task': 'paasdeploy.tasks.update_deployment_status',
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
        }
    },
    'BROKER_USE_SSL': True if os.environ.get('OMEGA_USESSL') else False,
}
#: celery task packages
OMEGA_CLOUD_CELERY_IMPORTS = ['paasdeploy', 'omegaops']
if 'beat' in sys.argv:
    # if this is the scheduler, make sure we include all omega tasks
    from omegaml import _base_config as omdefaults

    OMEGA_CLOUD_CELERY_IMPORTS += omdefaults.OMEGA_CELERY_IMPORTS
    print("*** OMEGA_CLOUD_CELERY_IMPORTS", OMEGA_CLOUD_CELERY_IMPORTS)
elif any(m in [basename(arg) for arg in sys.argv]
         # this is to avoid using production settings during test
         for m in ('unittest', 'test', 'nosetests', 'noserunner', '_jb_unittest_runner.py',
                   '_jb_nosetest_runner.py')):
    OMEGA_LOCAL_RUNTIME = True
