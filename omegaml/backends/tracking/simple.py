import dill
import importlib
import numpy as np
import os
import pandas as pd
import platform
import pymongo
import warnings
from base64 import b64encode, b64decode
from datetime import date
from itertools import chain
from typing import Iterable
from uuid import uuid4

from omegaml.backends.tracking.base import TrackingProvider
from omegaml.documents import Metadata
from omegaml.util import _raise, ensure_index, batched, signature, tryOr, ensurelist


class NoTrackTracker(TrackingProvider):
    """ A default tracker that does not record anything """

    def start(self, run=None):
        pass

    def stop(self):
        pass

    def log_artifact(self, obj, name, step=None, **extra):
        pass

    def log_metric(self, key, value, step=None, **extra):
        pass

    def log_param(self, key, value, step=None, **extra):
        pass

    def log_event(self, event, key, value, step=None, **extra):
        pass

    def log_extra(self, **kwargs):
        pass

    def log_data(self, **kwargs):
        pass

    def data(self, experiment=None, run=None, event=None, step=None, key=None, raw=False, **query):
        pass


class OmegaSimpleTracker(TrackingProvider):
    """ A tracking provider that logs to an omegaml dataset

    Usage::

        with om.runtime.experiment(provider='default') as exp:
            ...
            exp.log_metric('accuracy', .78)

    .. versionchanged:: 0.17
        any extra

    """
    _provider = 'simple'
    _experiment = None
    _startdt = None
    _stopdt = None
    _autotrack = False

    _ensure_active = lambda self, r: r if r is not None else _raise(
        ValueError('no active run, call .start() or .use() '))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log_buffer = []
        self.max_buffer = 10
        self._initialize_dataset()

    def active_run(self, run=None):
        """ set the lastest run as the active run

        Args:
            run (int|str): optional or unique task id, if None the
               latest active run will be set, or a new run is created if
               no active run exists.

        Returns:
            current run (int)
        """
        if run is None:
            latest = self._latest_run
            latest_is_active = (latest is not None and self.status(run=latest) == 'STARTED')
            self._run = latest if latest_is_active else self.start(run=None)
        else:
            self._run = run
        self._experiment = self._experiment or uuid4().hex
        return self._run

    def use(self, run=None):
        """ reuse the latest run instead of starting a new one

        semantic sugar for self.active_run()

        Returns:
            self
        """
        self.active_run(run=run)
        return self

    @property
    def autotrack(self):
        return self._autotrack

    @autotrack.setter
    def autotrack(self, value):
        self._autotrack = value

    @property
    def _latest_run(self):
        cursor = self.data(event='start', run='*', lazy=True)
        data = list(cursor.sort('data.run', -1).limit(1)) if cursor else None
        run = data[-1].get('data', {}).get('run') if data is not None and len(data) > 0 else None
        return run

    def status(self, run=None):
        """ status of a run

        Args:
            run (int): the run number, defaults to the currently active run

        Returns:
            status in 'STARTED', 'STOPPED'
        """
        self._run = run or self._run or self._latest_run
        data = self.data(event=['start', 'stop'], run=self._run, raw=True)
        no_runs = data is None or len(data) == 0
        has_stop = sum(1 for row in (data or []) if row.get('event') == 'stop')
        return 'PENDING' if no_runs else 'STOPPED' if has_stop else 'STARTED'

    def start(self, run=None, immediate=True):
        """ start a new run

        This starts a new run and logs the start event
        """
        self._run = run or (self._latest_run or 0) + 1
        self._startdt = datetime.utcnow()
        data = self._common_log_data('start', key=None, value=None, step=None, dt=self._startdt)
        self._write_log(data, immediate=immediate)
        return self._run

    def stop(self, flush=True):
        """ stop the current run

        This stops the current run and records the stop event
        """
        self._stopdt = datetime.utcnow()
        data = self._common_log_data('stop', key=None, value=None, step=None, dt=self._stopdt)
        self._write_log(data)
        self.flush() if flush else None

    def flush(self):
        # passing list of list, as_many=True => collection.insert_many() for speed
        if self.log_buffer:
            self._store.put(self.log_buffer, self._data_name,
                            noversion=True, as_many=True)
            self.log_buffer.clear()

    def clear(self, force=False):
        """ clear all data

        All data is removed from the experiment's dataset. This is not recoverable.

        Args:
            force (bool): if True, clears all data, otherwise raises an error

        Caution:
            * this will clear all data and is not recoverable

        Raises:
            AssertionError: if force is not True

        .. versionadded:: 0.16.2

        """
        assert force, "clear() requires force=True to prevent accidental data loss. This will clear all experiment data and is not recoverable."
        self._store.drop(self._data_name, force=True)
        self._initialize_dataset(force=True)

    def _common_log_data(self, event, key, value, step=None, dt=None, **extra):
        if isinstance(value, dict):
            # shortcut to resolve PassthroughDataset actual values
            # -- enables storing the actual values of a dataset passed as a PassthroughDataset
            # TODO: should this be the responsibility of SimpleTracker?
            if isinstance(value.get('args'), (list, tuple)):
                value['args'] = [getattr(arg, '_passthrough_data', arg) for arg in value['args']]
            if isinstance(value.get('kwargs'), dict):
                value['kwargs'] = {
                    k: getattr(v, '_passthrough_data', v) for k, v in value['kwargs'].items()
                }
        data = {
            'experiment': self._experiment,
            'run': self._ensure_active(self._run),
            'step': step,
            'event': event,
            'key': key or event,
            'value': value,
            'dt': dt or datetime.utcnow(),
            'node': os.environ.get('HOSTNAME', platform.node()),
            'userid': self.userid,
        }
        # add **extra, check for duplicate keys to avoid overwriting
        dupl_keys = set(data.keys()) & set(extra.keys())
        if dupl_keys:
            raise ValueError(f'duplicate extra keys : {dupl_keys}')
        data.update(extra)
        data.update(self._extra_log) if self._extra_log else None
        return data

    def _write_log(self, data, immediate=False):
        self.log_buffer.append(data)
        if immediate or len(self.log_buffer) > self.max_buffer:
            self.flush()

    def log_artifact(self, obj, name, step=None, dt=None, event=None, key=None, **extra):
        """ log any object to the current run

        Usage::

            # log an artifact
            exp.log_artifact(mydict, 'somedata')

            # retrieve back
            mydict_ = exp.restore_artifact('somedata')

        Args:
            obj (obj): any object to log
            name (str): the name of artifact
            step (int): the step, if any
            **extra: any extra data to log

        Notes:
            * bool, str, int, float, list, dict are stored as ``format=type``
            * Metadata is stored as ``format=metadata``
            * objects supported by ``om.models`` are stored as ``format=model``
            * objects supported by ``om.datasets`` are stored as ``format=dataset``
            * all other objects are pickled and stored as ``format=pickle``
        """
        event = event or 'artifact'
        key = key or name
        if isinstance(obj, (bool, str, int, float, list, dict)):
            format = 'type'
            rawdata = obj
        elif isinstance(obj, Metadata):
            format = 'metadata'
            rawdata = obj.to_json()
        elif self._model_store.get_backend_byobj(obj) is not None:
            objname = uuid4().hex
            meta = self._model_store.put(obj, f'.experiments/.artefacts/{objname}')
            format = 'model'
            rawdata = meta.name
        elif self._store.get_backend_byobj(obj) is not None:
            objname = uuid4().hex
            meta = self._store.put(obj, f'.experiments/.artefacts/{objname}')
            format = 'dataset'
            rawdata = meta.name
        else:
            try:
                rawdata = b64encode(dill.dumps(obj)).decode('utf8')
                format = 'pickle'
            except TypeError as e:
                rawdata = repr(obj)
                format = 'repr'
        value = {
            'name': name,
            'data': rawdata,
            'format': format
        }
        data = self._common_log_data(event, key, value, step=step, dt=dt, name=name, **extra)
        self._write_log(data)

    def log_event(self, event, key, value, step=None, dt=None, **extra):
        data = self._common_log_data(event, key, value, step=step, dt=dt, **extra)
        self._write_log(data)

    def log_param(self, key, value, step=None, dt=None, **extra):
        """ log an experiment parameter

        Args:
            key (str): the parameter name
            value (str|float|int|bool|dict): the parameter value
            step (int): the step
            **extra: any other values to store with event

        Notes:
            * logged as ``event=param``
        """
        data = self._common_log_data('param', key, value, step=step, dt=dt, **extra)
        self._write_log(data)

    def log_metric(self, key, value, step=None, dt=None, **extra):
        """ log a metric value

        Args:
            key (str): the metric name
            value (str|float|int|bool|dict): the metric value
            step (int): the step
            **extra: any other values to store with event

        Notes:
            * logged as ``event=metric``
        """
        data = self._common_log_data('metric', key, value, step=step, dt=dt, **extra)
        self._write_log(data)

    def log_data(self, key, value, step=None, dt=None, event=None, **extra):
        """ log x/y data for model predictions

        This is semantic sugar for log_artifact() using the 'data' event.

        Args:
            key (str): the name of the artifact
            value (any): the x/y data
            step (int): the step
            dt (datetime): the datetime
            event (str): the event, defaults to 'data'
            **extra: any other values to store with event

        Returns:
            None
        """
        event = event or 'data'
        self.log_artifact(value, key, step=step, dt=dt, key=key, event=event, **extra)

    def log_system(self, key=None, value=None, step=None, dt=None, **extra):
        """ log system data

        Args:
            key (str): the key to use, defaults to 'system'
            value (str|float|int|bool|dict): the parameter value
            step (int): the step
            **extra: any other values to store with event

        Notes:
            * logged as ``event=system``
            * logs platform, python version and list of installed packages
        """
        key = key or 'system'
        value = value or {
            'platform': platform.uname()._asdict(),
            'python': '-'.join((platform.python_implementation(),
                                platform.python_version())),
            'packages': ['=='.join((d.metadata['Name'], d.version))
                         for d in importlib.metadata.distributions()]
        }
        data = self._common_log_data('system', key, value, step=step, dt=dt, **extra)
        self._write_log(data)

    def log_extra(self, remove=False, **kwargs):
        """ add additional log information for every subsequent logging call

        Args:
            remove (bool): if True, removes the extra log information
            kwargs: any key-value pairs to log

        """
        self._extra_log = {} if self._extra_log is None else self._extra_log
        if not remove:
            self._extra_log.update(kwargs)
        elif kwargs:
            from collections import deque as consume
            deletions = (self._extra_log.pop(k, None) for k in kwargs)
            consume(deletions, maxlen=0)
        else:
            self._extra_log = {}

    def data(self, experiment=None, run=None, event=None, step=None, key=None, raw=False,
             lazy=False, since=None, end=None, batchsize=None, slice=None, **extra):
        """ build a dataframe of all stored data

        Args:
            experiment (str|list): the name of the experiment, defaults to its current value
            run (int|list|str|slice): the run(s) to get data back, defaults to current run, use 'all' for all,
               1-indexed since first run, or -1 indexed from latest run, can combine both. If run < 0
               would go before the first run, run 1 will be returned. A slice(start, stop) can be used
               to specify a range of runs.
            event (str|list): the event(s) to include
            step (int|list): the step(s) to include
            key (str|list): the key(s) to include
            raw (bool): if True returns the raw data instead of a DataFrame
            lazy (bool): if True returns the Cursor instead of data, ignores raw
            since (datetime|timedelta|str): only return data since this date. If both since and run are specified,
               only matches since the given date are returned. If since is a string it must be parseable
               by pd.to_datime, or be given in the format '<n><unit:[smhdwMqy]>' for relative times, or a timedelta object. See
               dtrelative() for details on relative times.
            end (datetime): only return data until this date
            batchsize (int): if specified, returns a generator yielding data in batches of batchsize,
               note that raw is respected, i.e. raw=False yields a DataFrame for every batch, raw=True
               yields a list of dicts
            slice (tuple): if specified, returns a slice of the data, e.g. slice=(10, 25) returns rows 10-25,
               the slice is applied after all other filters

        Returns:
            For lazy == False:
            * data (DataFrame) if raw == False
            * data (list of dicts) if raw == True
            * None if no data exists

            For lazy == True, no batchsize, regardless of raw:
                * data (Cursor) for any value of raw

            For lazy == True, with batchsize:
            * data(generator of list[dict]) if raw = True
            * data(generator of DataFrame) if raw = False

        .. versionchanged:: 0.16.2
            run supports negative indexing

	    .. versionchanged:: 0.17
            added batchsize

        .. versionchanged:: 0.17
            enabled the use of run='*' to retrieve all runs, equivalent of run='all'

        .. versionchanged:: 0.17
            enabled data(run=, start=, end=, since=), accepting range queries on run, dt and event#
        """
        from functools import cache
        experiment = experiment or self._experiment
        # -- flush all buffers before querying
        self.flush()
        # -- build filter
        if since is None:
            run = run if run is not None else self._run
            run = ensurelist(run) if not isinstance(run, str) and isinstance(run, Iterable) else run
            # actual run
            # -- run is 1-indexed, so we need to adjust for -1 indexing
            #    e.g. -1 means the latest run, -2 the run before that
            #    e.g. latest_run = 5, run=-1 means 5, run=-2 means 4 etc.
            # -- run can be a list, in which case we adjust run < 0 for each element
            # -- run can never be less than 1 (1-indexed), even if run << 0
            last_run = cache(
                lambda: int(self._latest_run or 0))  # PERF/consistency: memoize the last run per each .data() call
            relative_run = lambda r: max(1, 1 + last_run() + r)
            if isinstance(run, list) and any(r < 0 for r in run):
                run = [(r if r >= 0 else relative_run(r)) for r in run]
            elif isinstance(run, int) and run < 0:
                run = relative_run(run)
        filter = self._build_data_filter(experiment, run, event, step, key, since, end, extra)

        def read_data(cursor):
            data = pd.DataFrame.from_records(cursor)
            if 'dt' in data.columns:
                data['dt'] = pd.to_datetime(data['dt'], errors='coerce')
                data.sort_values('dt', inplace=True)
            return data

        def read_data_batched(cursor, batchsize, slice):
            from builtins import slice as t_slice
            if cursor is None:
                yield None
                return
            if slice:
                slice = (slice.start or 0, slice.stop or 0) if isinstance(slice, t_slice) else slice
                cursor.skip(slice[0])
                cursor.limit(slice[1] - slice[0])
                batchsize = batchsize or (slice[1] - slice[0])
            for rows in batched(cursor, batchsize):
                data = (r.get('data') for r in rows)
                yield read_data(data) if not raw else list(data)

        if batchsize or slice:
            data = self._store.get(self._data_name, filter=filter, lazy=True, trusted=signature(filter))
            data = read_data_batched(data, batchsize, slice)
            if slice and not batchsize:
                # try to resolve just one iteration
                data, _ = tryOr(lambda: (next(data), data.close()), (None, None))
        else:
            data = self._store.get(self._data_name, filter=filter, lazy=lazy, trusted=signature(filter))
            data = read_data(data) if data is not None and not lazy and not raw else data
        return data

    def _build_data_filter(self, experiment, run, event, step, key, since, end, extra):
        # build a filter for the data query, suitable for OmegaStore.get()
        filter = {}
        valid = lambda s: s is not None and str(s).lower() not in ('all', '*')
        # SEC: ensure all values are basic types, to prevent operator injection
        valid_types = (str, int, float, list, tuple, date, datetime)
        op = lambda s: {'$in': ensurelist(s)} if isinstance(s, (list, tuple, np.ndarray)) else ensure_type(s,
                                                                                                           valid_types)
        ensure_type = lambda v, t: v if isinstance(v, t) else str(v)
        if valid(experiment):
            filter['data.experiment'] = op(experiment)
        if valid(run):
            if isinstance(run, slice):
                filter['data.run'] = {'$gte': run.start, '$lte': run.stop}
            else:
                filter['data.run'] = op(run)
        if valid(event):
            filter['data.event'] = op(event)
        if valid(step):
            filter['data.step'] = op(step)
        if valid(key):
            filter['data.key'] = op(key)
        if valid(since):
            dtnow = getattr(self, '_since_dtnow', datetime.utcnow())
            if isinstance(since, str):
                since = tryOr(lambda: pd.to_datetime(since), lambda: dtrelative('-' + since, now=dtnow))
            elif isinstance(since, timedelta):
                since = dtnow - since
            elif isinstance(since, datetime):
                since = since
            else:
                raise ValueError(
                    f'invalid since value: {since}, must be datetime, timedelta or string in format "<n><unit:[smhdwMqy]>"')
            filter['data.dt'] = {'$gte': str(since.isoformat())}
        if valid(end):
            dtnow = getattr(self, '_since_dtnow', datetime.utcnow())
            if isinstance(end, str):
                end = tryOr(lambda: pd.to_datetime(end), lambda: dtrelative('+' + end, now=dtnow))
            elif isinstance(end, timedelta):
                end = dtnow + end
            elif isinstance(end, datetime):
                end = end
            else:
                raise ValueError(
                    f'invalid end value: {end}, must be datetime, timedelta or string in format "<n><unit:[smhdwMqy]>"')
            filter['data.dt'] = filter.setdefault('data.dt', {})
            filter['data.dt']['$lte'] = str(end.isoformat())
        for k, v in extra.items():
            if valid(v):
                fk = f'data.{k}'
                filter[fk] = op(v)
        return filter

    @property
    def dataset(self):
        return self._data_name

    @property
    def stats(self):
        from omegaml.backends.tracking.statistics import ExperimentStatistics
        return ExperimentStatistics(self)

    def summary(self, **kwargs):
        return self.stats.summary(**kwargs)

    def _initialize_dataset(self, force=False):
        # create indexes when the dataset is first created
        if not force and self._store.exists(self._data_name):
            return
        coll = self._store.collection(self._data_name)
        idxs = [
            {'data.run': pymongo.ASCENDING, 'data.event': pymongo.ASCENDING, 'data.key': pymongo.ASCENDING,
             'data.experiment': pymongo.ASCENDING},
            {'data.dt': pymongo.ASCENDING, 'data.event': pymongo.ASCENDING, 'data.key': pymongo.ASCENDING,
             'data.experiment': pymongo.ASCENDING},
            {'data.dt': pymongo.ASCENDING, 'data.event': pymongo.ASCENDING, 'data.experiment': pymongo.ASCENDING},
        ]
        for specs in idxs:
            ensure_index(coll, specs)

    def restore_artifact(self, *args, **kwargs):
        """ restore a specific logged artifact

        .. versionchanged:: 0.17
             deprecated, use exp.restore_artifacts() instead
        """
        warnings.warn('deprecated, use exp.restore_artifacts() instead', DeprecationWarning)
        restored = self.restore_artifacts(*args, **kwargs)
        return restored[-1] if restored else None

    def restore_artifacts(self, key=None, experiment=None, run=None, since=None, step=None, value=None, event=None,
                          name=None):
        """ restore logged artifacts

        Args:
            key (str): the name of the artifact as provided in log_artifact
            run (int): the run for which to query, defaults to current run
            since (datetime): only return data since this date
            step (int): the step for which to query, defaults to all steps in run
            value (dict|list): dict or list of dict, this value is used instead of
               querying data, use to retrieve an artifact from contents of ``.data()``

        Returns:
            list of restored objects

        Notes:
            * this will restore the artifact according to its type assigned
              by ``.log_artifact()``. If the type cannot be determined, the
              actual data is returned

        Updates:
            * since 0.17: return list of objects instead of last object
        """
        event = event or 'artifact'
        name = name or '*'
        if value is None:
            all_data = self.data(experiment=experiment, run=run, since=since, event=event,
                                 step=step, key=key, raw=True, name=name)
        else:
            all_data = [{'value': value}] if isinstance(value, dict) else value
        restored = []
        all_data = all_data or []
        for item in all_data:
            data = item.get('value')
            if data['format'] == 'type':
                obj = data['data']
            elif data['format'] == 'metadata':
                meta = self._store._Metadata
                obj = meta.from_json(data['data'])
            elif data['format'] == 'dataset':
                obj = self._store.get(data['data'])
            elif data['format'] == 'model':
                obj = self._model_store.get(data['data'])
            elif data['format'] == 'pickle':
                obj = dill.loads(b64decode((data['data']).encode('utf8')))
            else:
                obj = data.get('data', data)
            restored.append(obj)
        return restored

    def restore_data(self, key, run=None, event=None, since=None, concat=True, **extra):
        """ restore x/y data for model predictions

        This is semantic sugar for restore_artifacts() using the event='data' event.

        Args:
            key (str): the name of the artifact
            run (int): the run for which to query, defaults to current run
            event (str): the event, defaults to 'data'
            since (datetime): only return data since this date
            concat (bool): if True, concatenates the data into a single object,
               in this case all data must be of the same type. Defaults to True.
            **extra: any other values to store with event

        Returns:
            list of restored objects
        """
        event = event or 'data'

        def _concat(values):
            if values is None:
                return None
            if len(values) and isinstance(values[0], (pd.DataFrame, pd.Series)):
                ensure_df_or_series = lambda v: pd.Series(v) if isinstance(v, (np.ndarray, list)) else v
                return pd.concat((ensure_df_or_series(v) for v in values), axis=0)
            elif len(values) and isinstance(values[0], np.ndarray):
                return np.concatenate(values, axis=0)
            # chain seems to be the fastests approach
            # -- https://stackoverflow.com/a/56407963/890242
            return list(chain(*values))

        restored = self.restore_artifacts(run=run, key=key, event=event, since=since, **extra)
        return restored if not concat else _concat(restored)


from datetime import datetime, timedelta


def dtrelative(delta, now=None, as_delta=False):
    """ return a datetime relative to now

    Args:
        delta (str|timedelta): the relative delta, if a string, specify as '[+-]<n><unit:[smhdwMqy]>',
          e.g. '1d' for one day, '-1d' for one day ago, '+1d' for one day from now. Special cases:
          '-0y' means the beginning of the current year, '+0y' means the end of the current year.
          smhdwMqy = seconds, minutes, hours, days, weeks, months, quarters, years
        now (datetime): the reference datetime, defaults to datetime.utcnow()
        as_delta (bool): if True, returns a timedelta object, otherwise a datetime object

    Returns:
        datetime|timedelta: the relative datetime or timedelta
    """
    # Parse the numeric part and the unit from the specifier
    UNIT_MAP = {'s': 1,  # 1 second
                'm': 60,  # 1 minute
                'h': 60 * 60,  # 1 hour
                'd': 24 * 60 * 60,  # 1 day
                'w': 7 * 24 * 60 * 60,  # 1 week
                'n': 30 * 24 * 60 * 60,  # 1 month
                'q': 90 * 24 * 60 * 60,  # 1 quarter
                'y': 365 * 24 * 60 * 60}  # 1 year
    now = now or datetime.utcnow()
    error_msg = f"Invalid delta {delta}. Use a string of format '<n><unit:[hdwmqy]>' or timedelta object."
    if isinstance(delta, str):
        try:
            past = delta.startswith('-')
            delta = (delta
                     .replace('-', '')
                     .replace('+', '')  # Remove the sign
                     .replace(' ', '')  # Remove spaces
                     .replace('M', 'n')  # m is ambiguous, so we use n for month
                     .lower())
            num = int(delta[:-1])  # The numeric part
            units = UNIT_MAP.get(delta[-1])  # The last character
            if delta[-1] == 'y' and num == 0:
                # special case -0y means beginning of the year, +0y means end of the year
                dtdelta = (datetime(now.year, 1, 1) - now) if past else (datetime(now.year, 12, 31) - now)
            else:
                dtdelta = timedelta(seconds=num * units * (-1 if past else 1))
        except:
            raise ValueError(error_msg)
    elif isinstance(delta, timedelta):
        dtdelta = delta
    else:
        raise ValueError(error_msg)
    return now + dtdelta if not as_delta else dtdelta
