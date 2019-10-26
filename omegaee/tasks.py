from datetime import datetime

from celery.signals import (task_failure, task_postrun, task_prerun,
                            task_success)

from omegaee.util import log_task

non_logging_tasks = ['omegaops.tasks.log_event_task']


@task_prerun.connect
def task_prerun_handler(task_id, task, *args, **kwargs):
    if task.name not in non_logging_tasks:
        setattr(task.request, 'start_dt', datetime.now())
        setattr(task.request, 'user', task.om.defaults.OMEGA_USERID)


@task_success.connect
def task_success_handler(sender=None, result=None, **kwargs):
    if sender.name not in non_logging_tasks:
        log_task(sender, 'SUCCESS')


@task_failure.connect
def task_failure_handler(sender=None, result=None, **kwargs):
    if sender.name not in non_logging_tasks:
        log_task(sender, 'FAILURE')