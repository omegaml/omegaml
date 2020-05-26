from copy import deepcopy

import six
from celery import Task
from kombu.serialization import registry
from kombu.utils import cached_property


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
        self._om = None

    @property
    def om(self):
        # TODO do some more intelligent caching, i.e. by client/auth
        if self._om is None:
            from omegaml import get_omega_for_task
            bucket = self.request.kwargs.pop('__bucket', None)
            self._om = get_omega_for_task(self)[bucket]
        return self._om

    def get_delegate(self, name, kind='models'):
        get_delegate_provider = getattr(self.om, kind)
        return get_delegate_provider.get_backend(name, data_store=self.om.datasets)

    @property
    def delegate_args(self):
        return self.request.args

    @property
    def delegate_kwargs(self):
        return {k: v for k, v in six.iteritems(self.request.kwargs) if not k.startswith('__')}

    def __call__(self, *args, **kwargs):
        self.reset()
        return super().__call__(*args, **kwargs)

    def reset(self):
        # ensure next call will start over and get a new om instance
        self._om = None

    def on_failure(self, *args, **kwargs):
        self.reset()
        return super().on_failure(*args, **kwargs)

    def on_retry(self, *args, **kwargs):
        self.reset()
        return super().on_retry(*args, **kwargs)

    def on_success(self, *args, **kwargs):
        self.reset()
        return super().on_success(*args, **kwargs)


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
