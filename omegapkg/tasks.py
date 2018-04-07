"""
omega runtime script tasks
"""
from __future__ import absolute_import

import json

import datetime
from celery import Task
from celery import shared_task
from omegaml.runtime.auth import get_omega_for_task
from omegapkg import PythonPackageData

class NotebookTask(Task):
    abstract = True

    def on_success(self, retval, task_id, *args, **kwargs):
        om = self.om 
        args, kwargs = args[0:2]
        scriptname = args[0]
        meta = om.scripts.metadata(scriptname)
        attrs = meta.attributes
        attrs['state'] = 'SUCCESS'
        attrs['task_id'] = task_id
        meta.kind = PythonPackageData.KIND

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
        scriptname = args[0]
        meta = om.scripts.metadata(scriptname)
        attrs = meta.attributes
        attrs['state'] = 'FAILURE'
        attrs['task_id'] = task_id
        meta.kind = PythonPackageData.KIND

        if not kwargs:
            pass
        else:
            attrs['last_run_time'] = kwargs.get('run_at')
            attrs['next_run_time'] = kwargs.get('next_run_time')

        meta.attributes = attrs
        meta.save()


@shared_task(bind=True, base=NotebookTask)
def run_omega_script(self, scriptname, **kwargs):
    """
    runs omegaml job
    """
    self.om = om = get_omega_for_task(auth=kwargs.pop('auth', None))
    mod = om.scripts.get(scriptname)
    try:
        dtstart = datetime.datetime.now()
        result = mod.run(**kwargs)
        dtend = datetime.datetime.now()
        duration = dtend - dtstart
    except Exception as e:
        result = str(e)

    data = {
        'script': scriptname,
        'kwargs': kwargs,
        'result': result,
        'runtime': float(duration.seconds) + duration.microseconds / float(1e6),
        'started': dtstart.isoformat(),
    }
    return data


