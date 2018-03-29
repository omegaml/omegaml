"""
omega runtime model tasks 
"""
from __future__ import absolute_import

import os

from celery import Task
from celery import shared_task
from celery.signals import worker_process_init

from omegaml import signals
from omegaml.runtime.auth import get_omega_for_task


class OmegamlTask(Task):
    abstract = True

    def on_success(self, retval, task_id, *args, **kwargs):
        signals.mltask_end.send(sender=None, state="SUCCESS", task=self.name)

    def on_failure(self, retval, task_id, *args, **kwargs):
        signals.mltask_end.send(sender=None, state="FAILURE", task=self.name)


def get_dataset_representations(items):
    """
    returns dict with x and y datasets
    """
    results = {}
    results['Xname'] = items.get('Xname')
    results['Yname'] = items.get('Yname')
    return results


@shared_task(base=OmegamlTask)
def omega_predict(modelname, Xname, rName=None, pure_python=True, **kwargs):
    om = get_omega_for_task(auth=kwargs.pop('auth', None))
    backend = om.models.get_backend(modelname, data_store=om.datasets)
    result = backend.predict(modelname, Xname, rName, pure_python, **kwargs)
    signals.mltask_start.send(
        sender=None, name='omega_predict',
        args=get_dataset_representations(locals()))
    return result


@shared_task(base=OmegamlTask)
def omega_predict_proba(modelname, Xname, rName=None, pure_python=True,
                        **kwargs):
    om = get_omega_for_task(auth=kwargs.pop('auth', None))
    backend = om.models.get_backend(modelname, data_store=om.datasets)
    result = backend.predict_proba(
        modelname, Xname, rName, pure_python, **kwargs)
    signals.mltask_start.send(
        sender=None, name='omega_predict_proba',
        args=get_dataset_representations(locals()))
    return result


@shared_task(base=OmegamlTask)
def omega_fit(modelname, Xname, Yname=None, pure_python=True, **kwargs):
    om = get_omega_for_task(auth=kwargs.pop('auth', None))
    backend = om.models.get_backend(modelname, data_store=om.datasets)
    result = backend.fit(
        modelname, Xname, Yname, pure_python, **kwargs)
    signals.mltask_start.send(
        sender=None, name='omega_fit',
        args=get_dataset_representations(locals()))
    return result


@shared_task(base=OmegamlTask)
def omega_partial_fit(
        modelname, Xname, Yname=None, pure_python=True, **kwargs):
    om = get_omega_for_task(auth=kwargs.pop('auth', None))
    backend = om.models.get_backend(modelname, data_store=om.datasets)
    result = backend.partial_fit(
        modelname, Xname, Yname, pure_python, **kwargs)
    signals.mltask_start.send(
        sender=None, name='omega_partial_fit',
        args=get_dataset_representations(locals()))
    return result


@shared_task(base=OmegamlTask)
def omega_score(modelname, Xname, Yname, rName=True, pure_python=True,
                **kwargs):
    om = get_omega_for_task(auth=kwargs.pop('auth', None))
    backend = om.models.get_backend(modelname, data_store=om.datasets)
    result = backend.score(
        modelname, Xname, Yname, rName=rName, pure_python=pure_python,
        **kwargs)
    signals.mltask_start.send(
        sender=None, name='omega_score',
        args=get_dataset_representations(locals()))
    return result


@shared_task(base=OmegamlTask)
def omega_fit_transform(modelname, Xname, Yname=None, rName=None,
                        pure_python=True, **kwargs):
    om = get_omega_for_task(auth=kwargs.pop('auth', None))
    backend = om.models.get_backend(modelname, data_store=om.datasets)
    result = backend.score(
        modelname, Xname, Yname, rName, pure_python, **kwargs)
    signals.mltask_start.send(
        sender=None, name='omega_fit_transform',
        args=get_dataset_representations(locals()))
    return result


@shared_task(base=OmegamlTask)
def omega_transform(modelname, Xname, rName=None, **kwargs):
    om = get_omega_for_task(auth=kwargs.pop('auth', None))
    backend = om.models.get_backend(modelname, data_store=om.datasets)
    result = backend.transform(modelname, Xname, rName, **kwargs)
    signals.mltask_start.send(
        sender=None, name='omega_transform',
        args=get_dataset_representations(locals()))
    return result

@shared_task(base=OmegamlTask)
def omega_decision_function(modelname, Xname, rName=None, **kwargs):
    om = get_omega_for_task(auth=kwargs.pop('auth', None))
    backend = om.models.get_backend(modelname, data_store=om.datasets)
    result = backend.decision_function(modelname, Xname, rName, **kwargs)
    signals.mltask_start.send(
        sender=None, name='omega_decision_function',
        args=get_dataset_representations(locals()))
    return result


@shared_task(base=OmegamlTask)
def omega_settings():
    if os.environ.get('OMEGA_DEBUG'):
        from omegaml.util import settings
        defaults = settings()
        return {k: getattr(defaults, k, '')
                for k in dir(defaults) if k and k.isupper()}
    return {'error': 'settings dump is disabled'}


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
