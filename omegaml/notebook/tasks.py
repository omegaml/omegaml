"""
omega runtime job tasks
"""
from __future__ import absolute_import

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
def run_omegaml_job(self, nb_file, **kwargs):
    """
    runs omegaml job
    """
    result = self.om.jobs.run_notebook(nb_file)
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

    will retrieve all scripts from the mongodb
    (as per a respective OMEGAML_SCRIPTS_GRIDFS setting),
    provided they are marked for execution at the time of execution
    """
    om = self.om
    # Search tasks from mongo
    job_list = om.jobs.list()
    for nb_file in job_list:
        try:
            metadata = Metadata.objects.get(
                name=nb_file, kind=Metadata.OMEGAML_RUNNING_JOBS)
            task_state = metadata.attributes.get('state')
            if task_state == "RECEIVED":
                pass
            else:
                om.jobs.schedule(nb_file)
        except DoesNotExist:
            om.jobs.schedule(nb_file)
