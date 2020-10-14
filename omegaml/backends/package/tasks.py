"""
omega runtime script tasks
"""
from __future__ import absolute_import

import datetime
import json
from celery import shared_task

from omegaml.celery_util import OmegamlTask


class NotebookTask(OmegamlTask):
    abstract = True

    def on_success(self, retval, task_id, *args, **kwargs):
        om = self.om
        args, kwargs = args[0:2]
        scriptname = args[0]
        meta = om.scripts.metadata(scriptname)
        attrs = meta.attributes
        attrs['state'] = 'SUCCESS'
        attrs['task_id'] = task_id

        if not kwargs:
            pass
        else:
            attrs['last_run_time'] = kwargs.get('run_at')
            attrs['next_run_time'] = kwargs.get('next_run_time')

        meta.attributes = attrs
        meta.save()

    def on_failure(self, retval, task_id, *args, **kwargs):
        print("*** NotebookTask.on_failure (retval, task_id, args, kwargs)",
              retval, task_id, args, kwargs)
        om = self.om
        args, kwargs = args[0:2]
        scriptname = args[0]
        meta = om.scripts.metadata(scriptname)
        attrs = meta.attributes
        attrs['state'] = 'FAILURE'
        attrs['task_id'] = task_id

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
    SERIALIZER = {
        'json': json.dumps,
        'python': lambda v: v,
    }
    format = kwargs.get('__format') or 'json'
    mod = self.om.scripts.get(scriptname)
    dtstart = datetime.datetime.now()
    try:
        result = mod.run(self.om, **self.delegate_kwargs)
    except Exception as e:
        result = str(e)
    dtend = datetime.datetime.now()
    duration = dtend - dtstart

    data = {
        'script': scriptname,
        'kwargs': self.delegate_kwargs,
        'result': result,
        'runtimes': float(duration.seconds) + duration.microseconds / float(1e6),
        'started': dtstart.isoformat(),
        'ended': dtend.isoformat(),
    }
    return SERIALIZER[format](data)
