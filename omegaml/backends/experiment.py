import dill
import os
import pandas as pd
import warnings
from base64 import b64encode, b64decode
from datetime import datetime
from itertools import product
from uuid import uuid4

from omegaml.backends.basemodel import BaseModelBackend
from omegaml.documents import Metadata


class ExperimentBackend(BaseModelBackend):
    """ ExperimentBackend provides storage of tracker configurations

    Usage:
        Log data

            with om.runtime.experiment('myexp') as exp:
                om.runtime.model('mymodel').fit(X, Y)
                om.runtime.model('mymodel').score(X, Y) # automatically log score result
                exp.log_metric('mymetric', value)
                exp.log_param('myparam', value)
                exp.log_artifact(X, 'X')
                exp.log_artifact(Y, 'Y')
                exp.log_artifact(om.models.metadata('mymodel'), 'mymodel')

        Get back experiment data

            exp = om.models.get('experiments/myexp')
            exp_df = exp.data()

    See Also:

        TrackingProvider
        TrackingProxy
    """
    KIND = 'experiment.tracker'
    exp_prefix = 'experiments/'

    @classmethod
    def supports(self, obj, name, **kwargs):
        return isinstance(obj, TrackingProvider)

    def put(self, obj, name, **kwargs):
        name = f'{self.exp_prefix}{name}' if not name.startswith('experiments') else name
        # FIXME use proper pickle magic to avoid storing the store
        store = obj._store
        obj._store = None
        obj._model_store = None
        meta = super().put(obj, name, **kwargs)
        meta.attributes['dataset'] = obj._data_name
        meta.save()
        obj._store = store
        obj._model_store = self.model_store
        return meta

    def get(self, name, raw=False, data_store=None, **kwargs):
        assert data_store is not None, "experiments require a datastore, specify data_store=om.datasets"
        tracker = super().get(name, **kwargs)
        name = os.path.basename(name)
        tracker._store = data_store
        tracker._model_store = self.model_store
        return tracker.experiment(name) if not raw else tracker

    def drop(self, name, force=False, version=-1, data_store=None, **kwargs):
        data_store = data_store or self.data_store
        meta = self.model_store.metadata(name)
        dataset = meta.attributes.get('dataset')
        data_store.drop(dataset, force=True)
        return self.model_store._drop(name, force=force, version=version, **kwargs)


class TrackingProvider:
    """ TrackingProvider implements an abstract interface to experiment tracking

    Concrete implementations like MLFlow, Sacred or Neptune.ai can be implemented
    based on TrackingProvider. In combination with the runtime's OmegaTrackingProxy
    this provides a powerful tracking interface that scales with your needs.

    How it works:

        1. Experiments created using om.runtime.experiment() are stored as
           instances of a TrackingProvider concrete implementation

        2. Upon retrieval of an experiment, any call to its API is proxied to the
           actual implementation, e.g. MLFlow

        3. On calling a model method via the runtime, e.g. om.runtime.model().fit(),
           the TrackingProvider information is passed on to the runtime worker,
           and made available as the backend.tracking property. Thus within a
           model backend, you can always log to the tracker by using:

                with self.tracking as exp:
                    exp.log_metric() # call any TrackingProvider method

        4. To avoid complexity at project start, omega-ml provides the
           OmegaSimpleTracker, which provides a tracking interface similar
           to MLFlow and Sacred, however without the complexity. See ExperimentBackend
           for an example.
    """

    def __init__(self, experiment, store=None, model_store=None):
        self._experiment = experiment
        self._run = None
        self._store = store
        self._model_store = model_store

    def experiment(self, name=None):
        self._experiment = name or self._experiment
        return self

    def active_run(self):
        self._run = (self._run or 0) + 1
        return self._run

    def start(self):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def log_event(self, event, key, value, step=None, **extra):
        raise NotImplementedError

    def log_metric(self, key, value, step=None, **extra):
        raise NotImplementedError

    def log_artifact(self, obj, name, step=None, **extra):
        raise NotImplementedError

    def log_param(self, key, value, step=None, **extra):
        raise NotImplementedError

    def tensorflow_callback(self):
        return TensorflowCallback(self)

    def data(self, experiment=None, run=None, event=None, step=None, key=None, raw=False):
        raise NotImplementedError

    @property
    def _data_name(self):
        return f'.experiments/{self._experiment}'


class NoTrackTracker(TrackingProvider):
    """ A default tracker that does not record anything """

    def start(self):
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

    def data(self, experiment=None, run=None, event=None, step=None, key=None, raw=False):
        pass


class OmegaSimpleTracker(TrackingProvider):
    """ A tracking provider that logs to an omegaml dataset

    Usage:
        with
    """
    _provider = 'simple'
    _experiment = None
    _startdt = None
    _stopdt = None

    def active_run(self):
        self._run = self._latest_run or self.start()
        self._experiment = self._experiment or uuid4().hex
        return self

    @property
    def _latest_run(self):
        data = self.data(event='start', raw=True)
        run = data[-1]['run'] if data is not None and len(data) > 0 else None
        return run

    def start(self):
        self._run = (self._latest_run or 0) + 1
        self._startdt = datetime.utcnow()
        data = {
            'experiment': self._experiment,
            'run': self._run,
            'event': 'start',
            'dt': self._startdt,
        }
        self._store.put(data, self._data_name, noversion=True)
        return self._run

    def stop(self):
        self._stopdt = datetime.utcnow()
        data = {
            'experiment': self._experiment,
            'run': self._run,
            'event': 'stop',
            'dt': self._stopdt,
        }
        self._store.put(data, self._data_name, noversion=True)

    def log_artifact(self, obj, name, step=None, **extra):
        if isinstance(obj, (bool, str, int, float, list, dict)):
            format = 'type'
            rawdata = obj
        elif isinstance(obj, Metadata):
            format = 'metadata'
            rawdata = obj.to_json()
        elif self._model_store.get_backend_byobj(obj) is not None:
            objname = uuid4().hex
            meta = self._model_store.put(obj, f'experiments/.artefacts/{objname}')
            format = 'model'
            rawdata = meta.name
        elif self._store.get_backend_by_obj(obj) is not None:
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
        data = {
            'experiment': self._experiment,
            'run': self._run,
            'step': step,
            'event': 'artifact',
            'key': name,
            'value': {
                'name': name,
                'data': rawdata,
                'format': format
            },
            'dt': datetime.utcnow(),
        }
        self._store.put(data, self._data_name, noversion=True)

    def log_event(self, event, key, value, step=None, **extra):
        data = {
            'experiment': self._experiment,
            'run': self._run,
            'step': step,
            'event': event,
            'key': key,
            'value': value,
            'dt': datetime.utcnow(),
        }
        if step is not None:
            data['step'] = step
        data.update(extra)
        self._store.put(data, self._data_name, noversion=True)

    def log_param(self, key, value, step=None, **extra):
        data = {
            'experiment': self._experiment,
            'run': self._run,
            'step': step,
            'event': 'param',
            'key': key,
            'value': value,
            'dt': datetime.utcnow(),
        }
        if step is not None:
            data['step'] = step
        data.update(extra)
        self._store.put(data, self._data_name, noversion=True)

    def log_metric(self, key, value, step=None, **extra):
        data = {
            'experiment': self._experiment,
            'run': self._run,
            'step': step,
            'event': 'metric',
            'key': key,
            'value': value,
            'dt': datetime.utcnow(),
        }
        if step is not None:
            data['step'] = step
        data.update(extra)
        self._store.put(data, self._data_name)

    def data(self, experiment=None, run=None, event=None, step=None, key=None, raw=False):
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
        data = self._store.get(self._data_name, filter=filter)
        data = pd.DataFrame.from_records(data) if data is not None and not raw else data
        return data

    def restore_artifact(self, key=None, experiment=None, run=None, step=None, value=None):
        if value is None:
            data = self.data(experiment=experiment, run=run, event='artifact', step=step, key=key, raw=True)
            data = data[-1]['value']
        else:
            data = value
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
            obj = data['data']
        return obj


try:
    from tensorflow import keras
except:
    warnings.warn("tensorflow.keras could not be imported. Tracking support for Tensorflow is disabled. ")
else:
    class TensorflowCallback(keras.callbacks.Callback):
        # https://www.tensorflow.org/guide/keras/custom_callback
        def __new__(cls, *args, **kwargs):
            # generate methods as per specs
            for action, phase in product(['train', 'test', 'predict'], ['begin', 'end']):
                cls.wrap(f'on_{action}_{phase}', 'on_global')
                cls.wrap(f'on_{action}_batch_{phase}', 'on_batch')
            for phase in ['begin', 'end']:
                cls.wrap(f'on_epoch_{phase}', 'on_epoch')
            return super().__new__(cls)

        def __init__(self, tracker):
            self.tracker = tracker
            self.model = None

        def set_model(self, model):
            self.tracker.log_artifact(model, 'model')

        def set_params(self, params):
            for k, v in params.items():
                self.tracker.log_param(k, v)

        def on_global(self, action, logs=None):
            for k, v in logs.items():
                self.tracker.log_metric(k, v)

        def on_batch(self, action, batch, logs=None):
            for k, v in logs.items():
                self.tracker.log_metric(k, v, step=batch)

        def on_epoch(self, action, epoch, logs=None):
            for k, v in logs.items():
                self.tracker.log_metric(k, v, step=epoch)

        @classmethod
        def wrap(cls, method, fn):
            fn = getattr(cls, fn)

            def inner(self, *args, **kwargs):
                return fn(self, method, *args, **kwargs)

            setattr(cls, method, inner)
            return inner
