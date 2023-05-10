import os
import platform
import warnings
from base64 import b64encode, b64decode
from datetime import datetime
from uuid import uuid4

import dill
import pandas as pd
import pkg_resources
import pymongo

from omegaml.backends.tracking.base import TrackingProvider
from omegaml.documents import Metadata
from omegaml.util import _raise, ensure_index


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

    def data(self, experiment=None, run=None, event=None, step=None, key=None, raw=False):
        pass


class OmegaSimpleTracker(TrackingProvider):
    """ A tracking provider that logs to an omegaml dataset

    Usage::

        with om.runtime.experiment(provider='default') as exp:
            ...
            exp.log_metric('accuracy', .78)
    """
    _provider = 'simple'
    _experiment = None
    _startdt = None
    _stopdt = None

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
               latest active run will be set, or

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
    def _latest_run(self):
        cursor = self.data(event='start', lazy=True)
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

    def start(self, run=None):
        """ start a new run

        This starts a new run and logs the start event
        """
        self._run = run or (self._latest_run or 0) + 1
        self._startdt = datetime.utcnow()
        data = self._common_log_data('start', key=None, value=None, step=None, dt=self._startdt)
        self._write_log(data, immediate=True)
        return self._run

    def stop(self):
        """ stop the current run

        This stops the current run and records the stop event
        """
        self._stopdt = datetime.utcnow()
        data = self._common_log_data('stop', key=None, value=None, step=None, dt=self._stopdt)
        self._write_log(data)
        self.flush()

    def flush(self):
        # passing list of list forces insert_many
        if self.log_buffer:
            self._store.put(self.log_buffer, self._data_name,
                            noversion=True, as_many=True)
            self.log_buffer.clear()

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
        data.update(extra)
        data.update(self._extra_log) if self._extra_log else None
        return data

    def _write_log(self, data, immediate=False):
        self.log_buffer.append(data)
        if immediate or len(self.log_buffer) > self.max_buffer:
            self.flush()

    def log_artifact(self, obj, name, step=None, **extra):
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
        data = self._common_log_data('artifact', name, value, step=step, **extra)
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
            'packages': ['=='.join((d.project_name, d.version))
                         for d in pkg_resources.working_set]
        }
        data = self._common_log_data('system', key, value, step=step, dt=dt, **extra)
        self._write_log(data)

    def log_extra(self, remove=False, **kwargs):
        """ add additional log information for every subsequent logging call """
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
             lazy=False, **extra):
        """ build a dataframe of all stored data

        Args:
            experiment (str|list): the name of the experiment, defaults to its current value
            run (int|list): the run(s) to get data back, defaults to current run, use 'all' for all
            event (str|list): the event(s) to include
            step (int|list): the step(s) to include
            key (str|list): the key(s) to include
            raw (bool): if True returns the raw data instead of a DataFrame
            lazy (bool): if True returns the Cursor instead of data, ignores raw

        Returns:
            * data (DataFrame) if raw == False
            * data (list of dicts) if raw == True
            * None if no data exists
        """
        filter = {}
        experiment = experiment or self._experiment
        run = run or self._run
        valid = lambda s: s is not None and str(s).lower() != 'all'
        op = lambda s: {'$in': list(s)} if isinstance(s, (list, tuple)) else s
        if valid(experiment):
            filter['data.experiment'] = op(experiment)
        if valid(run):
            filter['data.run'] = op(run)
        if valid(event):
            filter['data.event'] = op(event)
        if valid(step):
            filter['data.step'] = op(step)
        if valid(key):
            filter['data.key'] = op(key)
        for k, v in extra.items():
            if valid(k):
                filter[f'data.{k}'] = op(v)
        data = self._store.get(self._data_name, filter=filter, lazy=lazy)
        if data is not None and not raw and not lazy:
            data = pd.DataFrame.from_records(data)
            if 'dt' in data.columns:
                data['dt'] = pd.to_datetime(data['dt'], errors='coerce')
                data.sort_values('dt', inplace=True)
        return data

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
        ensure_index(coll, {'data.run': pymongo.ASCENDING, 'data.event': pymongo.ASCENDING})

    def restore_artifact(self, *args, **kwargs):
        """ restore a specific logged artifact

        Updates:
            * since 0.17: Deprecated, use exp.restore_artifacts() instead
        """
        warnings.warn('deprecated, use exp.restore_artifacts() instead', DeprecationWarning)
        restored = self.restore_artifacts(*args, **kwargs)
        return restored[-1] if restored else None

    def restore_artifacts(self, key=None, experiment=None, run=None, step=None, value=None):
        """ restore logged artifacts

        Args:
            key (str): the name of the artifact as provided in log_artifact
            run (int): the run for which to query, defaults to current run
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
        if value is None:
            all_data = self.data(experiment=experiment, run=run, event='artifact',
                                 step=step, key=key, raw=True)
        else:
            all_data = [{'value': value}] if isinstance(value, dict) else value
        restored = []
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
