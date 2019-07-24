"""
omega runtime job tasks
"""
from __future__ import absolute_import

import datetime

from celery import shared_task
from mongoengine.errors import DoesNotExist

from omegaml.documents import Metadata
from omegaml.celery_util import OmegamlTask


class NotebookTask(OmegamlTask):
    abstract = True

    def on_success(self, retval, task_id, *args, **kwargs):
        om = self.om
        args, kwargs = args[0:2]
        nbfile = args[0]
        meta = om.jobs.metadata(nbfile)
        attrs = meta.attributes
        attrs['state'] = 'SUCCESS'
        attrs['task_id'] = task_id
        meta.kind = Metadata.OMEGAML_JOBS

        if not kwargs:
            pass
        else:
            attrs['last_run_time'] = kwargs.get('run_at')
            attrs['next_run_time'] = kwargs.get('next_run_time')

        meta.attributes = attrs
        meta.save()

    def on_failure(self, retval, task_id, *args, **kwargs):
        om = self.om
        args, kwargs = args[0:2]
        nbfile = args[0]
        meta = om.jobs.metadata(nbfile)
        attrs = meta.attributes
        attrs['state'] = 'FAILURE'
        attrs['task_id'] = task_id
        meta.kind = Metadata.OMEGAML_JOBS

        if not kwargs:
            pass
        else:
            attrs['last_run_time'] = kwargs.get('run_at')
            attrs['next_run_time'] = kwargs.get('next_run_time')

        meta.attributes = attrs
        meta.save()


@shared_task(bind=True, base=NotebookTask)
def run_omegaml_job(self, nb_file, event=None, **kwargs):
    """
    runs omegaml job
    """
    result = self.om.jobs.run_notebook(nb_file, event=event)
    return result.to_json()


@shared_task(base=NotebookTask, bind=True)
def schedule_omegaml_job(self, nb_file, **kwargs):
    """
    schedules the running of omegaml job
    """
    result = self.om.jobs.schedule(nb_file)
    return result


@shared_task(base=OmegamlTask, bind=True)
def execute_scripts(self, **kwargs):
    """
    run scheduled jobs
    """
    om = self.om
    now = kwargs.get('now') or datetime.datetime.now()
    # get pending tasks, execute if time is right
    for job_meta in om.jobs.list(raw=True):
        triggers = job_meta.attributes.get('triggers', [])
        # run pending jobs
        pending = (trigger for trigger in triggers
                   if trigger['event-kind'] == 'scheduled' and trigger['status'] == 'PENDING')
        for trigger in pending:
            run_at = trigger['run-at']
            if now >= run_at:
                task = om.runtime.job(job_meta.name).run(event=trigger['event'])
                trigger['taskid'] = task.id
                job_meta.save()
                # immediately schedule for next time
                om.jobs.schedule(job_meta.name, last_run=now)
                # ensure we execute at most one job at a time
                break
