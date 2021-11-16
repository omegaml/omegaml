import sys

import six
from celery import Task
from contextlib import contextmanager
from kombu.serialization import registry
from kombu.utils import cached_property

from omegaml.store.logging import OmegaLoggingHandler
from omegaml.util import tryOr


class EagerSerializationTaskMixin(object):
    # ensure eager tasks are being serialized to capture serialization errors
    # adopted from https://github.com/celery/celery/issues/4008#issuecomment-330292405
    abstract = True

    @cached_property
    def _not_eager(self):
        app = self._app
        return not app.conf.CELERY_ALWAYS_EAGER

    @cached_property
    def _task_serializer(self):
        app = self._app
        return app.conf.CELERY_TASK_SERIALIZER

    def apply_async(self, args=None, kwargs=None, *args_, **kwargs_):
        if self._not_eager:
            return super(EagerSerializationTaskMixin, self).apply_async(args=args, kwargs=kwargs, *args_, **kwargs_)
        # only execute if eager
        # -- perform a serialization / deserialization roundtrip, as we would in distributed mode (not eager)
        sargs, skwargs = self._eager_serialize_args(args=args, kwargs=kwargs, **kwargs_)
        sargs_, skwargs_ = self._eager_serialize_args(args=args_, kwargs=kwargs_, **kwargs_)
        # -- call actual task with deserialized args, kwargs, as it would be by remote
        result = super(EagerSerializationTaskMixin, self).apply_async(args=sargs, kwargs=skwargs, *sargs_, **skwargs_)
        # -- do the same for the result
        result = self._eager_serialize_result(result, **kwargs_)
        return result

    def _eager_serialize_args(self, args=None, kwargs=None, **kwargs_):
        # Perform a noop serialization backtrip to assert args and kwargs
        # will be serialized appropriately when an async call through kombu
        # is actually performed. This is done to make sure we catch the
        # serializations errors with our test suite which runs with the
        # CELERY_ALWAYS_EAGER setting set to True. See the following Celery
        # issue for details https://github.com/celery/celery/issues/4008.
        app = self._app
        producer = kwargs_.get('producer') if kwargs else None
        with app.producer_or_acquire(producer) as producer:
            serializer = kwargs_.get('serializer', producer.serializer) or self._task_serializer
            registry.enable(serializer)
            args_content_type, args_content_encoding, args_data = registry.dumps(args, serializer)
            kwargs_content_type, kwargs_content_encoding, kwargs_data = registry.dumps(kwargs, serializer)
            args = registry.loads(args_data, args_content_type, args_content_encoding)
            kwargs = registry.loads(kwargs_data, kwargs_content_type, kwargs_content_encoding)
        return args, kwargs

    def _eager_serialize_result(self, result, **kwargs_):
        app = self._app
        producer = kwargs_.get('producer') if kwargs_ else None
        result_value = result._result
        with app.producer_or_acquire(producer) as producer:
            serializer = kwargs_.get('serializer', producer.serializer) or self._task_serializer
            registry.enable(serializer)
            dtype, encoding, data = registry.dumps(result_value, serializer)
            result._result = registry.loads(data, dtype, encoding)
        return result


class OmegamlTask(EagerSerializationTaskMixin, Task):
    abstract = True

    def __init__(self, *args, **kwargs):
        super(OmegamlTask, self).__init__(*args, **kwargs)

    @property
    def om(self):
        # TODO do some more intelligent caching, i.e. by client/auth
        kwargs = self.request.kwargs or {}
        if not hasattr(self.request, '_om'):
            self.request._om = None
        if self.request._om is None:
            from omegaml import get_omega_for_task
            bucket = kwargs.pop('__bucket', None)
            self.request._om = get_omega_for_task(self)[bucket]
        return self.request._om

    def get_delegate(self, name, kind='models'):
        get_delegate_provider = getattr(self.om, kind)
        self.enable_delegate_tracking(name, kind, get_delegate_provider)
        result = get_delegate_provider.get_backend(name, data_store=self.om.datasets, tracking=self.tracking)
        return result

    def enable_delegate_tracking(self, name, kind, delegate_provider):
        exp = self.tracking.experiment
        meta = delegate_provider.metadata(name)
        exp.log_artifact(meta, 'related')
        tracking = meta.attributes.setdefault('tracking', {})
        tracking['experiments'] = set(tracking.get('experiments', []) + [exp._experiment])
        meta.save()
        return meta

    @property
    def delegate_args(self):
        return self.request.args

    @property
    def delegate_kwargs(self):
        return {k: v for k, v in six.iteritems(self.request.kwargs) if not k.startswith('__')}

    @property
    def tracking(self):
        if not hasattr(self.request, '_om_tracking'):
            self.request._om_tracking = None
        if self.request._om_tracking is None:
            kwargs = self.request.kwargs or {}
            experiment = kwargs.pop('__experiment', None)
            if experiment is not None:
                # we reuse implied_run=False to use the currently active run,
                # i.e. with block will NOT call exp.start()
                tracker = self.om.runtime.experiment(experiment, implied_run=False)
                self.request._om_tracking = tracker
            else:
                self.request._om_tracking = self.om.runtime.experiment('.notrack', provider='notrack')
        return self.request._om_tracking

    @property
    def logging(self):
        kwargs = self.request.kwargs or {}
        logging = kwargs.pop('__logging', False)
        if isinstance(logging, tuple):
            logname, level = logging
            if logname is True:
                logname = 'root'
        elif isinstance(logging, str):
            if logging.lower() in ('info', 'warn', 'fatal', 'error', 'debug', 'critical'):
                logname, level = 'root', logging.upper()
            else:
                logname, level = logging, 'INFO'
        elif logging is True:
            logname, level = 'root', 'INFO'
        else:
            logname, level = None, 'NOTSET'
        return logname, level

    def __call__(self, *args, **kwargs):
        import logging
        @contextmanager
        def task_logging():
            logname, level = self.logging
            if logname:
                self.om.logger.setLevel(level)
                logger = logging.getLogger(name=logname if logname != 'root' else None)
                logger.setLevel(level)
                save_stdout, save_stderr = sys.stdout, sys.stderr
                self.app.log.redirect_stdouts_to_logger(logger, loglevel=level)
                handler = OmegaLoggingHandler.setup(store=self.om.datasets,
                                                    logger=logger,
                                                    exit_hook=True,
                                                    level=level)
            else:
                logger = None
            try:
                yield
            finally:
                if logger:
                    handler.flush()
                    handler.close()
                    logger.removeHandler(handler)
                    # reset stdout redirects
                    sys.stdout, sys.stderr = save_stdout, save_stderr

        with task_logging():
            with self.tracking as exp:
                exp.log_event(f'task_call', self.name, {'args': args, 'kwargs': kwargs})
                result = super().__call__(*args, **kwargs)
        return result

    def reset(self):
        # ensure next call will start over and get a new om instance
        self.request._om = None

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        with self.tracking as exp:
            exp.log_event(f'task_failure', self.name, {
                'exception': repr(exc),
                'task_id': task_id,
            })
        self.reset()
        return super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_retry(self, exc, task_id, args, kwargs):
        with self.tracking as exp:
            exp.log_event(f'task_retry', self.name, {
                'exception': repr(exc),
                'task_id': task_id,
            })
        self.reset()
        return super().on_retry(exc, task_id, args, kwargs)

    def on_success(self, retval, task_id, args, kwargs):
        with self.tracking as exp:
            exp.log_event(f'task_success', self.name, {
                'result': sanitized(retval),
                'task_id': task_id,
            })
        self.reset()
        return super().on_success(retval, task_id, args, kwargs)


def get_dataset_representations(items):
    """
    returns dict with x and y datasets
    """
    results = {}
    results['Xname'] = items.get('Xname')
    results['Yname'] = items.get('Yname')
    return results


def sanitized(value):
    # fix because local Metadata object cannot be pickled
    if getattr(type(value), '__name__', None) == 'Metadata':
        value = repr(value)
    return value
