"""
omega runtime job tasks
"""
from __future__ import absolute_import

import datetime
from celery import shared_task
from celery.utils.log import get_task_logger
from omegaml.celery_util import OmegamlTask, sanitized
from omegaml.documents import MDREGISTRY


class NotebookTask(OmegamlTask):
    abstract = True

    def on_success(self, retval, task_id, *args, **kwargs):
        try:
            om = self.om
            task_args, task_kwargs = args[0:2]
            nbfile = task_args[0]
            meta = om.jobs.metadata(nbfile)
            attrs = meta.attributes
            attrs['state'] = 'SUCCESS'
            attrs['task_id'] = task_id
            meta.kind = MDREGISTRY.OMEGAML_JOBS
            if not task_kwargs:
                pass
            else:
                attrs['last_run_time'] = task_kwargs.get('run_at')
                attrs['next_run_time'] = task_kwargs.get('next_run_time')

            meta.attributes = attrs
            meta.save()
        except:
            pass
        finally:
            super().on_success(retval, task_id, *args, **kwargs)

    def on_failure(self, retval, task_id, *args, **kwargs):
        try:
            om = self.om
            task_args, task_kwargs = args[0:2]
            nbfile = task_args[0]
            meta = om.jobs.metadata(nbfile)
            attrs = meta.attributes
            attrs['state'] = 'FAILURE'
            attrs['task_id'] = task_id
            meta.kind = MDREGISTRY.OMEGAML_JOBS

            if not task_kwargs:
                pass
            else:
                attrs['last_run_time'] = task_kwargs.get('run_at')
                attrs['next_run_time'] = task_kwargs.get('next_run_time')

            meta.attributes = attrs
            meta.save()
        except:
            pass
        finally:
            super().on_failure(retval, task_id, *args, **kwargs)


@shared_task(bind=True, base=NotebookTask)
def run_omegaml_job(self, nb_file, event=None, timeout=None, **kwargs):
    """
    runs omegaml job
    """
    result = self.om.jobs.run_notebook(nb_file, event=event, timeout=timeout)
    return sanitized(result)


@shared_task(base=NotebookTask, bind=True)
def schedule_omegaml_job(self, nb_file, **kwargs):
    """
    schedules the running of omegaml job
    """
    result = self.om.jobs.schedule(nb_file, run_at=kwargs.get('run_at'))
    return sanitized(result)


@shared_task(base=OmegamlTask, bind=True)
def execute_scripts(self, **kwargs):
    """
    run scheduled jobs

    .. versionchanged:: 0.16.4
       hidden jobs are now included in the list of jobs to run
    """
    logger = get_task_logger(self.name)
    om = self.om
    now = kwargs.get('now') or datetime.datetime.now()
    # get pending tasks, execute if time is right
    for job_meta in om.jobs.list(raw=True, hidden=True):
        if job_meta.name.startswith('results'):
            # ignore any scheduled results
            continue
        logger.debug("***** {}".format(job_meta))
        triggers = job_meta.attributes.get('triggers', [])
        # run pending jobs
        pending = (trigger for trigger in triggers
                   if trigger['event-kind'] == 'scheduled' and trigger['status'] == 'PENDING')
        for trigger in pending:
            run_at = trigger['run-at']
            logger.info("***** now={} run_at={}".format(now, run_at))
            if now >= run_at:
                om.runtime.job(job_meta.name).run(event=trigger['event'])
                # immediately schedule for next time
                om.jobs.schedule(job_meta.name, last_run=now)
