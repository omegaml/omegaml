"""
omega runtime model tasks
"""
from __future__ import absolute_import

import datetime
import os
import sys
from celery import shared_task
from celery.signals import worker_process_init

from omegaml.celery_util import OmegamlTask, sanitized

if os.path.basename(sys.argv[0]) == 'celery':
    try:
        # ensure tensorflow is loaded -- this avoids AttributeError for tf.estimator later
        # we do this here instead of in tfestimatormodel to avoid loading tensorflow if it
        # is not needed. loading means this happens at runtime worker startup
        import tensorflow as tf

        tf.version
    except:
        pass


@shared_task(base=OmegamlTask, bind=True)
def omega_predict(self, modelname, Xname, rName=None, pure_python=True, **kwargs):
    result = self.get_delegate(modelname).perform('predict', *self.delegate_args, **self.delegate_kwargs)
    return sanitized(result)


@shared_task(base=OmegamlTask, bind=True)
def omega_reduce(self, results, modelName=None, rName=None, pure_python=True, **kwargs):
    result = self.get_delegate(modelName).perform('reduce', modelName, results, **self.delegate_kwargs)
    return sanitized(result)


@shared_task(base=OmegamlTask, bind=True)
def omega_predict_proba(self, modelname, Xname, rName=None, pure_python=True, **kwargs):
    result = self.get_delegate(modelname).perform('predict_proba', *self.delegate_args, **self.delegate_kwargs)
    return sanitized(result)


@shared_task(base=OmegamlTask, bind=True)
def omega_fit(self, modelname, Xname, Yname=None, pure_python=True, **kwargs):
    result = self.get_delegate(modelname).perform('fit', *self.delegate_args, **self.delegate_kwargs)
    return sanitized(result)


@shared_task(base=OmegamlTask, bind=True)
def omega_partial_fit(self,
                      modelname, Xname, Yname=None, pure_python=True, **kwargs):
    result = self.get_delegate(modelname).perform('partial_fit', *self.delegate_args, **self.delegate_kwargs)
    return sanitized(result)


@shared_task(base=OmegamlTask, bind=True)
def omega_score(self, modelname, Xname, Yname=None, rName=True, pure_python=True,
                **kwargs):
    result = self.get_delegate(modelname).perform('score', *self.delegate_args, **self.delegate_kwargs)
    return sanitized(result)


@shared_task(base=OmegamlTask, bind=True)
def omega_fit_transform(self, modelname, Xname, Yname=None, rName=None,
                        pure_python=True, **kwargs):
    result = self.get_delegate(modelname).perform('fit_transform', *self.delegate_args, **self.delegate_kwargs)
    return sanitized(result)


@shared_task(base=OmegamlTask, bind=True)
def omega_transform(self, modelname, Xname, rName=None, **kwargs):
    result = self.get_delegate(modelname).perform('transform', *self.delegate_args, **self.delegate_kwargs)
    return sanitized(result)


@shared_task(base=OmegamlTask, bind=True)
def omega_decision_function(self, modelname, Xname, rName=None, **kwargs):
    result = self.get_delegate(modelname).perform('decision_function', *self.delegate_args, **self.delegate_kwargs)
    return sanitized(result)


@shared_task(base=OmegamlTask, bind=True)
def omega_gridsearch(self, modelname, Xname, Yname=None, parameters=None, **kwargs):
    result = self.get_delegate(modelname).perform('gridsearch', *self.delegate_args, **self.delegate_kwargs)
    return sanitized(result)


@shared_task(base=OmegamlTask, bind=True)
def omega_settings(self, *args, **kwargs):
    if os.environ.get('OMEGA_DEBUG'):
        defaults = self.om.defaults
        return {k: getattr(defaults, k, '')
                for k in dir(defaults) if k and k.isupper()}
    return {'error': 'settings dump is disabled'}


@shared_task(base=OmegamlTask, bind=True)
def omega_ping(task, *args, logging=False, **kwargs):
    import socket
    hostname = task.request.hostname or socket.gethostname()
    # resolve standard kwargs
    om = task.om
    args = task.delegate_args
    kwargs = task.delegate_kwargs
    kwargs.pop('pure_python', None)
    # return ping
    data = {
        'message': 'ping return message',
        'time': datetime.datetime.now().isoformat(),
        'args': args,
        'kwargs': kwargs,
        'worker': hostname,
    }
    logname, level = task.logging
    if logname:
        import logging as logmod
        pylevel = getattr(logmod, level)
        # test omega, task and package level loggers
        om.logger.setLevel(level)
        om.logger.log(level, f'omega log: running ping task {data}')
        task_logger = task.app.log.get_default_logger()
        task_logger.log(pylevel, f'python log: running ping task {data}')
        package_logger = task.app.log.get_default_logger('omegaml')
        package_logger.log(pylevel, f'package log: running ping task {data}')
        print(f"print log: running ping task {data}")
    return data


@worker_process_init.connect
def fix_multiprocessing(**kwargs):
    # allow celery to start sub processes
    # this is required for sklearn joblib unpickle support
    # issue see https://github.com/celery/billiard/issues/168
    # fix source https://github.com/celery/celery/issues/1709
    from multiprocessing import current_process
    try:
        current_process()._config
    except AttributeError:
        current_process()._config = {'semprefix': '/mp'}
