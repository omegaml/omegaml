import atexit
import platform

import logging
import os
import signal
from pymongo import WriteConcern
from pymongo.read_concern import ReadConcern

LOGGER_HOSTNAME = os.environ.get('HOSTNAME') or platform.node()


class OmegaLoggingHandler(logging.Handler):
    """
    A Python logging handler that writes to a dataset

    You should only use this if you are familiar with Python logging
    and you are sure you need its flexibility. In most cases using
    om.logger is the better solution.

    Usage:
        # in ipython
        handler = OmegaLoggingHandler.setup(reset=True)
        handler = handler.tail()

        # if you want to attach to a specific logger
        logger = logging.getLogger(__file__)
        handler = OmegaLoggingHandler.setup(reset=True, logger=logger)

        # if omega is initialized other than om.setup()
        handler = OmegaLoggingHandler.setup(store=om.datasets)
        df = om.logger.dataset.get()

    See Also:
        OmegaSimpleLogger for notes about the log dataset format
    """

    def __init__(self, store, dataset, collection, level=None):
        super().__init__()
        level = level or logging.INFO
        self.store = store
        self.collection = collection
        self.dataset = dataset
        self.setLevel(level)

    def emit(self, record):
        log_entry = _make_record(record.levelname, record.levelno, record.name,
                                 record.msg, text=self.format(record),
                                 hostname=getattr(record, 'hostname', LOGGER_HOSTNAME))
        self.collection.insert_one(log_entry)

    def tail(self, wait=False):
        return TailableLogDataset(dataset=self.dataset, collection=self.collection).tail(wait=wait)

    @classmethod
    def setup(cls, store=None, dataset=None, level=None, logger=None, name=None,
              fmt=None, reset=False, size=10 * 1024 * 1024, defaults=None, exit_hook=False):
        """
        Args:
            dataset (str): the name of the dataset
            level (int): set any logging.INFO, logging.ERROR, logging.DEBUG, defaults to NOTSET
            size (int): maxium size in bytes (defaults to 1MB)
            target (Omega): omega instance to create the dataset in, defaults to the default om
            size (int): the maximum size of the log in bytes (capped), defaults to 1MB, set to -1
               for
            name (str): the logger name, defaults to omegaml, set to __name__ for current module
            reset (bool): recreate the logging dataset
            fmt (str): the format specification
            exit_hook (bool): when True attach the logger to the system exception handler
        """
        import omegaml as om
        import logging
        effective_level = logger.getEffectiveLevel() if logger else logging.NOTSET
        logger_name = name or 'omegaml'
        level = level or effective_level
        store = store or om.setup().datasets
        defaults = defaults or store.defaults
        dataset = dataset or defaults.OMEGA_LOG_DATASET
        fmt = fmt or defaults.OMEGA_LOG_FORMAT
        # setup handler and logger
        logger = logger or logging.getLogger(logger_name)
        collection = _setup_logging_dataset(store, dataset, logger=logger, size=size, reset=reset)
        formatter = logging.Formatter(fmt)
        handler = OmegaLoggingHandler(store, dataset, collection, level=level)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        if exit_hook:
            _attach_sysexcept_hook(logger)
        return handler


class OmegaSimpleLogger:
    """
    om.logger implementation

    This is a simplified logger for client code that does not rely
    on standard python logging. Use this instead of print()

    Usage:
        # in your code, e.g. in a runtime script or in a notebook
        om.logger.info(message)
        om.logger.critical(message)
        om.logger.error(message)
        om.logger.warning(message)
        om.logger.debug(message)

        # get the log contents
        df = om.logger.dataset.get() # returns a DataFrame of the log

        # filter on specific levels
        df = om.logger.dataset.get(levelname='INFO')

        # tail the log
        om.logger.dataset.tail()

        # from the command line
        $ om runtime log
        $ om runtime log -f

        # get a named logger
        # -- by default the logger's name is "simple", you can specify any other name
        om.logger.name = 'myname'
        # or get different loggers for differt names, e.g. by module
        logger = om.logger.getLogger('myname')

    Notes:
        The log contents is written to the omegaml dataset .omega/logs. You
        should not need to interact with this dataset.

        The format of the dataframe returned by om.logger.dataset.get() is
        as follows:

            levelname (str): the log level, e.g. INFO, DEBUG, WARNING, ERROR
            levelno (int): the level as a numberic, where DEBUG is highest.
            message (str): the message as passed to the logger methods
            text (str): the formatted message, including timestamp
            created (datetime): the UTC datetime of the log message

        Tailing the log is based on querying the latest message created, and
        then subsequently returning all newer messages. The tailing is
        implemented by TailableLogDataset and runs in a separate thread. To
        run the tailing as a blocking command use

        om.logger.dataset.tail(wait=True).
    """
    levels = 'QUIET,CRITICAL,ERROR,WARNING,INFO,DEBUG'.split(',')

    def __init__(self, store=None, dataset=None, collection=None, level='INFO',
                 size=1 * 1024 * 1024, defaults=None, name='simple'):
        import omegaml as om

        self.store = store or om.setup().datasets
        self.defaults = defaults or store.defaults
        self.dsname = dataset or self.defaults.OMEGA_LOG_DATASET
        self._dataset = None
        self._level = None
        self.setLevel(level)
        self._is_setup = False
        self._collection = collection
        self.size = size
        self._name = name

    @property
    def collection(self):
        if not self._is_setup:
            self._collection = _setup_logging_dataset(self.store, self.dsname, self,
                                                      collection=self._collection, size=self.size)
            self._is_setup = True
        return self._collection

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name

    def getLogger(self, name, **kwargs):
        return self.__class__(store=kwargs.get('store', self.store),
                              defaults=kwargs.get('defaults', self.defaults),
                              name=name)

    def setLevel(self, level):
        """
        choose a level, itself and all levels to the left of it will be logged

        Usage:
            e.g. setLevel('DEBUG') => DEBUG, INFO, WARNING, ERROR, CRITICAL
                           INFO    => INFO, WARNING, ERROR, CRITICAL
                           WARNING => WARNING, ERROR, CRITICAL
                           ERROR   => ERROR, CRITICAL
                           CRITICAL => CRITICAL

        Args:
            level (str): the level threshold

        Returns:
            None
        """
        self._level = self.levels.index(level)

    @property
    def level(self):
        return self.levels[self._level]

    def log(self, level, message):
        """
        simple logger function, use instead of print()
        """
        # check log level is below threshold (note this is reversed)
        levelno = self.levels.index(level)
        if levelno > self._level:
            return
        # insert a log message
        fmt = '{created} {level} {message}'
        log_entry = _make_record(level, levelno, self._name, message, fmt=fmt)
        self.collection.insert_one(log_entry)

    def info(self, message, **kwargs):
        self.log('INFO', message, **kwargs)

    def error(self, message, **kwargs):
        self.log('ERROR', message, **kwargs)

    def debug(self, message, **kwargs):
        self.log('DEBUG', message, **kwargs)

    def warning(self, message, **kwargs):
        self.log('WARNING', message, **kwargs)

    def critical(self, message, **kwargs):
        self.log('CRITICAL', message, **kwargs)

    @property
    def dataset(self):
        if self._dataset is None:
            self._dataset = TailableLogDataset(self.store,
                                               dataset=self._dataset,
                                               collection=self.collection)
        return self._dataset

    def exit_hook(self):
        _attach_sysexcept_hook(self)


class TailableLogDataset:
    """
    A threaded log tailer

    Usage:
        om.logger.dataset.get()
        om.logger.dataset.tail()
    """

    def __init__(self, store, dataset=None, collection=None, stdout=None):
        logger = self
        self.store = store
        self.dataset = dataset or store.defaults.OMEGA_LOG_DATASET
        self.collection = _setup_logging_dataset(store, self.dataset, logger, collection=collection)
        self.stdout = stdout
        self.tail_thread = None

    def __repr__(self):
        return "TailableLogDataset(dataset='{self.dataset}')".format(**locals())

    def tail(self, wait=False):
        return self._start(wait=wait)

    def stop(self):
        self.tail_stop = True

    def get(self, **kwargs):
        return self.store.get(self.dataset, **kwargs)

    def _start(self, wait=False):
        from threading import Thread
        from time import sleep

        # set stdout, must be file-like, implementing .write() and .flush()
        stdout = self.stdout if self.stdout is not None else self._get_fixed_stdout()
        # start tail thread
        self.tail_thread = Thread(target=self._tailer,
                                  args=(self.collection, stdout,))
        self.tail_thread.start()
        self.tail_stop = False
        # register exit handler to stop thread
        atexit.register(self._stop_handler)
        for sig in ('SIGHUP', 'SIGBREAK', 'SIGINT'):
            if hasattr(signal, sig):
                signal.signal(signal.SIGHUP, self._stop_handler)
        # block if requested
        if wait:
            while wait:
                sleep(1)
            self.tail_stop = True
        return self

    def _stop_handler(self, *args):
        self.stop()

    def _tailer(self, collection, stdout):
        # this runs in a thread to tail the log
        # adopted from https://api.mongodb.com/python/current/examples/tailable.html
        from time import sleep
        import pymongo

        def printer(record, stdout=stdout):
            print(str(record.get('text')), file=stdout, flush=True)

        first = collection.find().sort('$natural', pymongo.DESCENDING).limit(1).next()
        created = first.get('created')
        printer(first)

        while not self.tail_stop:
            cursor = collection.find({'created': {'$gt': created}})
            for record in cursor:
                printer(record)
                created = record.get('created')
                if self.tail_stop:
                    break
            sleep(.1)
        print("*** log tailing ended")

    def _get_fixed_stdout(self):
        """
        this is to support ipykernel stdout
        """
        import sys
        from ipykernel import iostream

        if isinstance(sys.stdout, iostream.OutStream):
            stdout = iostream.OutStream(sys.stdout.session,
                                        sys.stdout.pub_thread,
                                        'omega-logger')
            parent = dict(sys.stdout.parent_header)
            stdout.set_parent(parent)
        else:
            stdout = sys.stdout
        return stdout


def _make_record(level, levelno, name, message, text=None, fmt='{message}', hostname=None):
    from datetime import datetime
    created = datetime.utcnow()
    text = text if text is not None else fmt.format(**locals())
    hostname = hostname or LOGGER_HOSTNAME
    return {
        'levelname': level,
        'levelno': levelno,
        'name': name,
        'msg': message,
        'text': text,
        'created': created,
    }


def _setup_logging_dataset(store, dsname, logger, collection=None, size=10 * 1024 * 1024, reset=False):
    # setup the dataset
    assert dsname, 'need a valid dsname, got {}'.format(dsname)
    if reset:
        store.drop(dsname, force=True)
    collection = collection or store.collection(dsname)
    # https://api.mongodb.com/python/current/api/pymongo/write_concern.html#pymongo.write_concern.WriteConcern
    FireAndForget = WriteConcern(w=0)
    ReadFast = ReadConcern('local')
    collection = collection.with_options(write_concern=FireAndForget, read_concern=ReadFast)
    store.put(collection, dsname)
    if collection.estimated_document_count() == 0:
        # initialize. we insert directly into the collection because the logger instance is not set up yet
        record = _make_record('SYSTEM', 999, 'system', 'log init', 'log init')
        collection.insert_one(record)
        store.mongodb.command('convertToCapped', collection.name, size=size)
    # ensure indexed
    idxs = collection.index_information()
    for idx in ('levelname', 'levelno', 'created'):
        if idx not in idxs:
            collection.create_index(idx)
    return collection


def _attach_sysexcept_hook(logger):
    import traceback, sys
    sys.excepthook = lambda t, v, tb: logger.errro('{t} {v} {tb}'.format(t=t, v=v, tb=traceback.format_tb(tb)))
