import getpass

import sys
from celery import Task
from contextlib import contextmanager
from kombu.serialization import registry
from kombu.utils import cached_property

from omegaml.client.auth import AuthenticationEnv
from omegaml.store.logging import OmegaLoggingHandler


class EagerSerializationTaskMixin(object):
    # ensure eager tasks are being serialized to capture serialization errors
    # adopted from https://github.com/celery/celery/issues/4008#issuecomment-330292405
    abstract = True

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
        self.auth_env = AuthenticationEnv.active()

    @property
    def om(self):
        if not hasattr(self.request, '_om'):
            self.request._om = None
        if self.request._om is None:
            bucket = self.system_kwargs.get('__bucket')
            auth = self.system_kwargs.get('__auth')
            om = self.request._om = self.auth_env.get_omega_for_task(self, auth=auth)[bucket]
            # TODO link the global om to this actual linked om instance
            # -- this ensure that import omegaml as om will use the correct instance, including the bucket
            # -- might have unintended side effects, e.g. usually the global om is the default instance/bucket
            # -- to be tested before enabling.
            # -- alternative: make this a respnosibility of get_omega_for_task, passing the bucket as kwarg
            # link(om)
            self.auth_env.prepare_env(om.defaults)
            self.request._auth = om.runtime.auth
            # TODO the runtime should be set to the task's actual label (routing key)
            #      so that any user code using om.runtime is using the same label, e.g. for tracking
            # om.runtime.require(label=self.request.label)
        return self.request._om

    def get_delegate(self, name, kind='models', pass_as='model_store'):
        get_delegate_provider = getattr(self.om, kind)
        self.enable_delegate_tracking(name, kind, get_delegate_provider)
        kwargs = dict(data_store=self.om.datasets,
                      tracking=self.tracking)
        kwargs[pass_as] = get_delegate_provider
        result = get_delegate_provider.get_backend(name, **kwargs)
        return result

    def enable_delegate_tracking(self, name, kind, delegate_provider):
        exp = self.tracking.experiment
        meta = delegate_provider.metadata(name)
        exp.log_artifact(meta, 'related')
        meta = delegate_provider.link_experiment(name, exp._experiment)
        return meta

    @property
    def current_userid(self):
        # TODO: move current_userid to authenenv
        return getattr(self.request._auth, 'userid', getpass.getuser())

    @property
    def delegate_args(self):
        return self.request.args

    @property
    def delegate_kwargs(self):
        kwargs = self.request.kwargs or {}
        return {k: v for k, v in kwargs.items() if not k.startswith('__')}

    @property
    def system_kwargs(self):
        kwargs = self.request.kwargs or {}
        return {k: v for k, v in kwargs.items() if k.startswith('__')}

    @property
    def tracking(self):
        if not hasattr(self.request, '_om_tracking'):
            self.request._om_tracking = None
        if self.request._om_tracking is None:
            kwargs = self.request.kwargs or {}
            experiment = kwargs.get('__experiment')
            if experiment is not None:
                # we reuse implied_run=False to use the currently active run,
                # i.e. with block will NOT call exp.start() if an experiment is already running
                tracker = self.om.runtime.experiment(experiment, implied_run=False)
                tracker.log_extra(taskid=self.request.id, userid=self.current_userid)
                self.request._om_tracking = tracker
            else:
                self.request._om_tracking = self.om.runtime.experiment('.notrack', provider='notrack')
        return self.request._om_tracking

    @property
    def logging(self):
        kwargs = self.request.kwargs or {}
        logging = kwargs.get('__logging', False)
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
                prev_level = logger.level
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
            except Exception as e:
                # in case of DEBUG logging enabled, output exception
                if logger and logger.isEnabledFor(logging.ERROR):
                    import traceback
                    tb = traceback.format_exc() if logger.isEnabledFor(logging.DEBUG) else ''
                    msg = f'{e}\n{tb}'
                    logger.error(msg)
                raise
            finally:
                if logger:
                    handler.flush()
                    handler.close()
                    logger.removeHandler(handler)
                    logger.setLevel(prev_level)
                    # reset stdout redirects
                    sys.stdout, sys.stderr = save_stdout, save_stderr

        with self.om.request(request=self.request), task_logging():
            # start experiment block, if required
            # -- this ensures we call exp.start() / exp.stop() if the task was started in context
            #    of this celery task
            with self.tracking as exp:
                # log task call event
                # -- only log delegate args, kwargs
                # -- avoid logging internal arguments
                exp.log_event(f'task_call', self.name, {'args': self.delegate_args,
                                                        'kwargs': self.delegate_kwargs})
                if self.request.id is not None:
                    # PERFTUNED
                    # if we have a request, avoid super().__call__()
                    # calling super() removes the request.id, which means our request._om caching does not work
                    # Rationale: https://github.com/celery/celery/issues/2633#issuecomment-286694356
                    result = self.run(*args, **self.delegate_kwargs)
                else:
                    # PERFISSUE new task cannot access the request cache, new omega instance is created
                    # if we don't have a request.id it means we don't have a proper callstack
                    # so we need to create one using super().__call__
                    # this may happen when calling tasks directly, such as in run_omega_callback_script
                    result = super().__call__(*args, **kwargs)
        return result

    def reset(self):
        # ensure next call will start over and get a new om instance
        self.request._om = None
        self.request._om_tracking = None
        self.auth_env.prepare_env(None, clear=True)
        # note we do not reset self.request._auth to preserve the user context for logging purpose

    def send_event(self, type, **fields):
        # ensure result masking in events
        if 'result' in fields:
            fields['result'] = AuthenticationEnv().active().resultauth(fields['result'])
        super().send_event(type, **fields)

    # processing task outcome and flushing the tracking buffer improves task latency
    # because celery only calls the on_* methods once the task results have been stored
    # downside is we risk losing the tracking buffer contents in case of an exception
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        try:
            with self.tracking as exp:
                exp.log_event(f'task_failure', self.name, {
                    'exception': repr(exc),
                    'task_id': task_id,
                })
                exp.log_extra(taskid=None, userid=None, remove=True)
                exp.flush()
        finally:
            super().on_failure(exc, task_id, args, kwargs, einfo)
            self.reset()

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        try:
            with self.tracking as exp:
                exp.log_event(f'task_retry', self.name, {
                    'exception': repr(exc),
                    'task_id': task_id,
                })
                exp.log_extra(taskid=None, userid=None, remove=True)
                exp.flush()
        finally:
            super().on_retry(exc, task_id, args, kwargs)
            self.reset()

    def on_success(self, retval, task_id, args, kwargs):
        # on task success the experiment is stopped already (if we started it)
        try:
            exp = self.tracking
            exp.log_event(f'task_success', self.name, {
                'result': sanitized(retval),
                'task_id': task_id,
            })
            exp.log_extra(taskid=None, userid=None, remove=True)
            exp.flush()
        finally:
            super().on_success(retval, task_id, args, kwargs)
            self.reset()


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
