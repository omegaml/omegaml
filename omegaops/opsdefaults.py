import os

import sys

OMEGA_BROKER = (os.environ.get('OMEGA_BROKER') or
                os.environ.get('RABBITMQ_URL') or
                'amqp://guest@127.0.0.1:5672//')

#: the celery backend name or URL
OMEGA_RESULT_BACKEND = 'amqp'

OMEGA_CLOUD_CELERY_CONFIG = {
    'CELERY_ACCEPT_CONTENT': ['pickle', 'json', 'msgpack', 'yaml'],
    'BROKER_URL': OMEGA_BROKER,
    'CELERY_RESULT_BACKEND': OMEGA_RESULT_BACKEND,
    'CELERY_ALWAYS_EAGER': False if 'OMEGA_BROKER' in os.environ else True,
    'CELERYBEAT_SCHEDULE': {
        'deploy_pending_services': {
            'task': 'paasdeploy.tasks.deploy_pending_services',
            'schedule': 10,
            'options': {
                'queue': 'omegaops',
            }
        },
        'execute_pending_tasks': {
            'task': 'paasdeploy.tasks.execute_pending_tasks',
            'schedule': 10,
            'options': {
                'queue': 'omegaops',
            }
        },
        'update_deployment_status': {
            'task': 'paasdeploy.tasks.update_deployment_status',
            'schedule': 10,
            'options': {
                'queue': 'omegaops',
            }
        },
        'run_user_scheduler': {
            'task': 'omegaops.tasks.run_user_scheduler',
            'schedule': 60,
            'options': {
                'queue': 'omegaops',
            }
        }
    },
}
#: celery task packages
OMEGA_CLOUD_CELERY_IMPORTS = ['paasdeploy', 'omegaops']
if 'beat' in sys.argv:
    # if this is the scheduler, make sure we include all omega tasks
    from omegaml import _base_config as omdefaults

    OMEGA_CLOUD_CELERY_IMPORTS += omdefaults.OMEGA_CELERY_IMPORTS
print("*** OMEGA_CLOUD_CELERY_IMPORTS", OMEGA_CLOUD_CELERY_IMPORTS)
