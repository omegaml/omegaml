"""
omega runtime script tasks
"""
from __future__ import absolute_import

import datetime
from celery import shared_task

from omegaml.celery_util import OmegamlTask
from omegaml.util import json_dumps_np


class ScriptTask(OmegamlTask):
    abstract = True

    def _get_script_metadata(self, args, kwargs):
        om = self.om
        scriptname, *args = args
        meta = om.scripts.metadata(scriptname)
        return meta

    def on_success(self, retval, task_id, args, kwargs):
        meta = self._get_script_metadata(args, kwargs)
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

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        meta = self._get_script_metadata(args, kwargs)
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


class CallbackScriptTask(ScriptTask):
    def _get_script_metadata(self, args, kwargs):
        om = self.om
        *args, scriptname = args
        meta = om.scripts.metadata(scriptname)
        return meta


@shared_task(bind=True, base=ScriptTask)
def run_omega_script(self, scriptname, *args, **kwargs):
    """
    runs omegaml job
    """
    # setup options
    SERIALIZER = {
        'json': json_dumps_np,
        'python': lambda v: v,
    }
    format = self.system_kwargs.get('__format') or 'json'
    # call and measure time
    dtstart = datetime.datetime.now()
    try:
        result = (self.get_delegate(scriptname, kind='scripts', pass_as='data_store')
                  .perform('run', scriptname, *self.delegate_args[1:], om=self.om, **self.delegate_kwargs))
    except Exception as e:
        import traceback
        if kwargs.get('__traceback') or self.logging[-1].lower() == 'debug':
            result = "".join(traceback.TracebackException.from_exception(e).format())
        else:
            result = repr(e)
        exception = True
    else:
        exception = False
    dtend = datetime.datetime.now()
    duration = dtend - dtstart
    # prepare result
    data = {
        'script': scriptname,
        'args': self.delegate_args[1:],
        'kwargs': self.delegate_kwargs,
        'result': result,
        'runtimes': float(duration.seconds) + duration.microseconds / float(1e6),
        'started': dtstart.isoformat(),
        'ended': dtend.isoformat(),
    }
    data = SERIALIZER[format](data)
    if exception:
        raise RuntimeError(data)
    return data


@shared_task(bind=True, base=CallbackScriptTask)
def run_omega_callback_script(self, *args, **kwargs):
    """
    runs omegaml job
    """
    # callbacks have the result first, then the original arguments
    # -- thus scriptname is the last(!) argument
    # -- https://docs.celeryq.dev/en/stable/userguide/canvas.html#callbacks
    if len(args) >= 3:
        results = args[0:-2]
        state = args[-2]
        scriptname = args[-1]
    else:
        results = args[0]
        state = 'SUCCESS'
        scriptname = args[-1]
    # include hidden (__key=value) kwargs, e.g. for logging, bucket, experiment
    # so that the run_omega_script task context sets up a proper omega instance
    full_kwargs = kwargs
    full_kwargs.update(self.system_kwargs)
    return run_omega_script(scriptname, state=state, results=results, **full_kwargs)
