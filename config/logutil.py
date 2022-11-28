"""
standardized logging configuration for multiple frameworks

Features
- configured from a common logging.yaml
- adds the global LoggingRequestContext, available as logutil.context
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
"""
from pathlib import Path

import logging
import os
import socket
import uuid
import yaml

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

    logging_config = (logging_config or getattr(settings, 'LOGGING_CONFIG_FILE', None)
                      or os.environ.get('LOGGING_CONFIG_FILE') or LOGUTIL_CONFIG_FILE)
    try:
        with open(logging_config, 'r') as fin:
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
        logging.info('logging initialized')
    return loggingConfig


def logutil_flask(app, mapping=None, **extra):
    # https://flask.palletsprojects.com/en/2.2.x/api/#signals
    from flask import request_started, request_tearing_down  # noqa
    from flask import request  # noqa

    def starter(*args, **kwargs):
        requestId = request.headers.get('x-request-id') or uuid.uuid4().hex
        LoggingRequestContext.start(requestId=requestId)

    request_started.connect(LoggingRequestContext.link_up(starter=starter, mapping=mapping, **extra), app)
    request_tearing_down.connect(LoggingRequestContext.link_down(), app)


def logutil_django(mapping=None, **extra):
    from django.core.signals import request_started, request_finished, got_request_exception  # noqa

    def starter(sender, environ, **kwargs):
        requestId = environ.get('HTTP_X_REQUEST_ID') or uuid.uuid4().hex
        LoggingRequestContext.start(requestId=requestId)

    request_started.connect(LoggingRequestContext.link_up(starter=starter, mapping=mapping, **extra))
    request_finished.connect(LoggingRequestContext.link_down())
    got_request_exception.connect(LoggingRequestContext.link_down())


def logutil_celery(mapping=None, **extra):
    from celery.signals import task_prerun, task_postrun

    def starter(task_id, task, *args, **kwargs):
        LoggingRequestContext.start(requestId=task_id)

    task_prerun.connect(LoggingRequestContext.link_up(starter=starter, mapping=mapping, **extra))
    task_postrun.connect(LoggingRequestContext.link_down())


class LoggingRequestContext:
    current = None
    mapping = {}
    extra = {
        'hostname': socket.gethostname(),
    }
    extra.update({k.lower(): v for k, v in os.environ.items() if k in LOGUTIL_ENV_KEYS})

    def __init__(self, **extra):
        LoggingRequestContext.current = self
        self.__dict__['data'] = {}
        self.gather(**extra)

    @classmethod
    def start(cls, **extra):
        cls.current = LoggingRequestContext(**extra)

    @classmethod
    def stop(cls, *args, **kwargs):
        cls.current.clear() if cls.current else None
        cls.current = LoggingRequestContext()

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
        if LoggingRequestContext.current:
            LoggingRequestContext.current.gather(**self.extra)
            LoggingRequestContext.current.mapping.update(self.mapping)
            for k, v in LoggingRequestContext.current.data.items():
                setattr(record, k, v)
            for tgt, src in LoggingRequestContext.current.mapping.items():
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
        else:
            record.__dict__.setdefault('task_name', '???')
            record.__dict__.setdefault('task_id', '???')
        return True


context = LoggingRequestContext.current = LoggingRequestContext()
requestContextFilter = lambda *args, **kwargs: LoggingRequestContextFilter(**kwargs)
hostnameFilter = lambda *args, **kwargs: HostnameInjectingFilter()
taskFilter = lambda *args, **kwargs: TaskInjectingFilter()
