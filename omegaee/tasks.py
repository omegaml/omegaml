from celery.signals import (task_failure, task_prerun,
                            task_success)
from datetime import datetime

from omegaee.util import log_task


def should_log(task):
    return task.name.startswith('omegaml.tasks')


@task_prerun.connect
def task_prerun_handler(task_id, task, *args, **kwargs):
    if should_log(task):
        auth = task.request.kwargs.get('__auth')
        username = auth[0] if auth else None
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

