"""
omega runtime model tasks
"""
from __future__ import absolute_import

import datetime
import inspect
import os
from celery import shared_task
from celery.signals import worker_process_init
from pathlib import Path

from omegaml.celery_util import OmegamlTask, sanitized


@shared_task(base=OmegamlTask, bind=True)
def omega_predict(self, modelname, Xname, rName=None, pure_python=True, **kwargs):
    result = self.get_delegate(modelname).perform('predict', *self.delegate_args, **self.delegate_kwargs)
    return sanitized(result)


@shared_task(base=OmegamlTask, bind=True)
def omega_complete(self, modelname, Xname, rName=None, pure_python=True, stream=False, **kwargs):
    result = self.get_delegate(modelname).perform('complete', *self.delegate_args, **self.delegate_kwargs)
    if inspect.isgenerator(result):
        chunk = {'result': None}
        stream = self.om.streams.get(f'.system/complete/{self.request.id}')
        for chunk in result:
            stream.append(chunk)
        result = {
            'result': chunk,
        }
    return sanitized(result)


@shared_task(base=OmegamlTask, bind=True)
def omega_embed(self, modelname, Xname, rName=None, pure_python=True, **kwargs):
    result = self.get_delegate(modelname).perform('embed', *self.delegate_args, **self.delegate_kwargs)
    return sanitized(result)


@shared_task(base=OmegamlTask, bind=True)
def omega_housekeep_indexembeddings(self):
    """ insert uploaded documents pending to be embedded
    """
    om = self.om

    def files_to_index():
        for meta in om.datasets.list('documents/*', raw=True):
            if not meta.attributes.get('indexed'):
                yield meta

    def index_file(meta):
        index_name = meta.attributes.get('index')
        index = om.datasets.get(index_name, model_store=om.models)
        file_path = Path(self.om.defaults.OMEGA_TMP) / '.uploads' / meta.name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, mode='wb') as fout:
            filelike = om.datasets.get(meta.name)
            fout.write(filelike.read())
        index.insert(file_path)
        meta.attributes['indexed'] = True
        meta.save()

    for meta in files_to_index():
        index_file(meta)

    # Get file information
    timestamp = str(int(datetime.time.time()))
    # Create document record
    document = {
        'id': timestamp,
        'original_name': filename,
        'stored_name': unique_filename,
        'file_path': file_path,
        'size': file_size,
        'size_formatted': format_file_size(file_size),
        'type': file_type,
        'index_name': index_name,
        'upload_date': utcnow().isoformat(),
        'status': 'uploaded'
    }
    # add document to index
    index = om.datasets.get(index_name, model_store=om.models)
    index.insert(file_path)


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
def omega_ping(task, *args, exception=False, **kwargs):
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
    if exception:
        raise RuntimeError("intentional exception caused by exception=True kwarg")
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


@shared_task(base=OmegamlTask, bind=True)
def omega_preload(task, *args, items=None, **kwargs):
    """ preload models, datasets and other items into worker process """
    pass


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


@worker_process_init.connect
def preload_frameworks(**kwargs):
    # TODO in light of PR#253 startup-performance this may be needed
    #      until then omegaml.defaults does this already, kept here for reference
    from omegaml import _base_config
    _base_config.load_framework_support()
