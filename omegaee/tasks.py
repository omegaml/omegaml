from datetime import datetime

import re
from celery.signals import (task_failure, task_prerun,
                            task_success, worker_process_init)

from omegaee.util import log_task

def should_log(task):
    return task.name.startswith('omegaml.tasks')


@task_prerun.connect
def task_prerun_handler(task_id, task, *args, **kwargs):
    if should_log(task):
        if hasattr(task, 'om'):
            username = getattr(task.om.defaults, 'OMEGA_USERID', None)
        else:
            username = None
        setattr(task.request, 'start_dt', datetime.now())
        setattr(task.request, 'user', username)


@task_success.connect
def task_success_handler(sender=None, **kwargs):
    if should_log(sender):
        log_task(sender, 'SUCCESS')


@task_failure.connect
def task_failure_handler(sender=None, exception=None, **kwargs):
    if should_log(sender):
        log_task(sender, 'FAILURE', exception=exception)

