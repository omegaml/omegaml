from datetime import datetime

from celery.signals import (task_failure, task_prerun,
                            task_success, worker_process_init, setup_logging)

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


@worker_process_init.connect
def disable_result_logging(**kwargs):
    # disable celery tracing of task outputs
    # https://stackoverflow.com/a/63548174/890242
    from celery.app import trace
    trace.LOG_SUCCESS = """\
    Task %(name)s[%(id)s] succeeded in %(runtime)ss\
    """


@setup_logging.connect
def config_loggers(*args, **kwargs):
    from config.logutil import configure_logging, logutil_celery
    configure_logging()
    logutil_celery()
