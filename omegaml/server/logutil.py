"""
standardized logging configuration for multiple frameworks

Features
- configured from a common logging.yaml
- adds the global LoggingRequestContext, available as logutil.context()
  for any component to update current loggable data
- request start/stop handlers to update the context per-request, including
  request and task id (celery)
- request-independent logging attributes, e.g. hostname or other **extra log data
- json and text logging by configuration
- mapping of logging record attributes to other attributes
- selective dropping of logging record attributes

How to use:

# 1. create /app/logging.yaml
# 2. make it known
$ export LOGUTIL_CONFIG_FILE=/app/logging.yaml

Django:

    in your AppConfig:

        def ready(self):
            configure_logging(settings=settings)
            logutil_django()

Flask:

    in your create_app():

        app = Flask()
        configure_logging(settings=app.config)
        logutil_flask(app)


Celery:

    in your tasks.py

    @setup_logging.connect
    def config_loggers(*args, **kwargs):
        configure_logging()
        logutil_celery()


To update logging data:

    from logutil import LoggingRequestContext
    LoggingRequestContext.inject(**data)
"""
import logging
import os
import socket
import threading
import uuid
import yaml
from pathlib import Path

#: list of os env keys that are logged, if available
LOGUTIL_ENV_KEYS = ['APP', 'APP_VERSION', 'APP_ENV', 'HOSTNAME']
#: optional additional env keys to be logged, if available
LOGUTIL_ENV_KEYS += os.environ.get('LOGUTIL_ENV_KEYS', '').split(',')
#: the logger.yaml location, defaults to the location of logutil.py
LOGUTIL_CONFIG_FILE = Path(__file__).parent / 'logging.yaml'


def configure_logging(logging_config=None, settings=None):
    """ configure logging

    This will read the logging configuration from LOGGING_CONFIG_FILE or fallback to settings.LOGGING.
    It will use logging.dictConfig to initialize logging accordingly. settings.LOGGING will be set to
    the logging configuration used. In a nutshell, this is a thin wrapper around logging.dictConfig()
    using a yaml file as its source.

    Args:
        logging_config (path): optional, /path/to/logging.yaml, defaults to env LOGGING_CONFIG_FILE
        settings (obj): optional, provide django.settings or flask.config to use settings.LOGGING_CONFIG_FILE,
           or fallback to settings.LOGGING
    """
    from logging.config import dictConfig

    config_file = (logging_config or getattr(settings, 'LOGGING_CONFIG_FILE', None)
                   or os.environ.get('LOGGING_CONFIG_FILE') or LOGUTIL_CONFIG_FILE)
    try:
        with open(config_file, 'r') as fin:
            loggingConfig = yaml.safe_load(fin)
            loggingConfig = loggingConfig.get('logging', loggingConfig)
    except Exception as e:
        logging.error(f"WARNING: Logging config failed due to {e}", exc_info=e)
        loggingConfig = {}
    if loggingConfig:
        try:
            dictConfig(loggingConfig)
        except Exception as e:
            logging.warning(f'could not initialize logging configuration due to {e}')
        else:
            setattr(settings, 'LOGGING', loggingConfig) if settings else None
        logging.info(f'logging initialized from {config_file}')
        logging.debug(f'logging config is {loggingConfig}')
    return loggingConfig


def logutil_flask(app, mapping=None, **extra):
    # https://flask.palletsprojects.com/en/2.2.x/api/#signals
    import flask
    from flask import request_started, request_tearing_down  # noqa

    def starter(*args, **kwargs):
        requestId = flask.request.headers.get(request_header_id) or uuid.uuid4().hex
        setattr(flask.request, '_requestid', requestId)
        LoggingRequestContext.start(requestId=requestId)

    request_header_id = app.config.get('REQUEST_ID_HEADER', 'x-request-id')
    request_started.connect(LoggingRequestContext.link_up(starter=starter, mapping=mapping, **extra), app)
    request_tearing_down.connect(LoggingRequestContext.link_down(), app)


def logutil_django(mapping=None, **extra):
    from django.core.signals import request_started, request_finished, got_request_exception  # noqa
    from django.conf import settings

    def starter(sender, environ, **kwargs):
        requestId = environ.get(request_header_id) or uuid.uuid4().hex
        environ[_header_id] = requestId
        LoggingRequestContext.start(requestId=requestId)

    _header_id = getattr(settings, 'REQUEST_ID_HEADER', 'X_REQUEST_ID').replace('-', '_')
    request_header_id = 'HTTP_{}'.format(_header_id)
    request_started.connect(LoggingRequestContext.link_up(starter=starter,
                                                          mapping=mapping,
                                                          **extra), weak=False)
    request_finished.connect(LoggingRequestContext.link_down(), weak=False)
    got_request_exception.connect(LoggingRequestContext.link_down(), weak=False)


def logutil_celery(mapping=None, **extra):
    from celery.signals import task_prerun, task_postrun

    def starter(task_id, task, *args, **kwargs):
        LoggingRequestContext.start(requestId=task_id)

    task_prerun.connect(LoggingRequestContext.link_up(starter=starter, mapping=mapping, **extra))
    task_postrun.connect(LoggingRequestContext.link_down())


class LoggingRequestContext:
    mapping = {}
    extra = {
        'hostname': socket.gethostname(),
    }
    extra.update({k.lower(): v for k, v in os.environ.items() if k in LOGUTIL_ENV_KEYS})

    def __init__(self, **extra):
        self.__dict__['data'] = {}
        self.gather(**extra)

    @classmethod
    def current(cls):
        _context.current = getattr(_context, 'current', None) or LoggingRequestContext()
        return _context.current

    @classmethod
    def start(cls, **extra):
        _context.current = LoggingRequestContext(**extra)

    @classmethod
    def stop(cls, *args, **kwargs):
        _context.current = LoggingRequestContext()

    @classmethod
    def link_up(cls, starter=None, mapping=None, **extra):
        extra.update(extra.pop('extra', {}))
        cls.mapping = mapping or cls.mapping or {}
        cls.extra.update(extra)
        return starter or cls.start

    @classmethod
    def link_down(cls):
        return cls.stop

    def gather(self, **extra):
        self.__dict__['data'].update(LoggingRequestContext.extra)
        self.__dict__['data'].update(extra)

    def clear(self):
        self.__dict__['data'].clear()

    def update(self, **extra):
        self.__dict__['data'].update(extra)

    @classmethod
    def inject(cls, **data):
        cls.current().update(**data)

    def __setattr__(self, key, value):
        self.__dict__['data'][key] = value

    def __getattr__(self, key):
        return self.__dict__['data'][key]


class LoggingRequestContextFilter(logging.Filter):
    def __init__(self, name='', mapping={}, extra={}, drop=[], **kwargs):
        super().__init__(name=name)
        self.mapping = mapping
        self.extra = extra
        self.drop = drop

    def filter(self, record):
        context = LoggingRequestContext.current()
        if context:
            context.gather(**self.extra)
            context.mapping.update(self.mapping)
            for k, v in context.data.items():
                setattr(record, k, v)
            for tgt, src in context.mapping.items():
                setattr(record, tgt, getattr(record, src, os.environ.get(src)))
            for k in self.drop:
                if hasattr(record, k):
                    delattr(record, k)
        return True


class HostnameInjectingFilter(logging.Filter):
    def __init__(self):
        self.hostname = socket.gethostname()

    def filter(self, record):
        record.hostname = self.hostname
        return True


class TaskInjectingFilter(logging.Filter):
    def filter(self, record):
        from celery._state import get_current_task
        task = get_current_task()
        if task and task.request:
            record.__dict__.update(task_id=task.request.id,
                                   task_name=task.name,
                                   user_id=getattr(task, 'current_userid', '???'))
        return True


_context = threading.local()
_context.current = LoggingRequestContext()
requestContextFilter = lambda *args, **kwargs: LoggingRequestContextFilter(**kwargs)
hostnameFilter = lambda *args, **kwargs: HostnameInjectingFilter()
taskFilter = lambda *args, **kwargs: TaskInjectingFilter()
