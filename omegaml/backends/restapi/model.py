import numpy as np
import pandas as pd
from celery.states import UNREADY_STATES
from omegaml.util import ensure_json_serializable
from time import sleep

from minibatch.tests.util import LocalExecutor


class GenericModelResource(object):
    def __init__(self, om, is_async=False):
        self.om = om
        self.is_async = is_async

    def is_eager(self):
        return getattr(self.om.runtime.celeryapp.conf, 'CELERY_ALWAYS_EAGER', False)

    def metadata(self, model_id, query, payload):
        meta = self.om.models.metadata(model_id)
        if meta is not None:
            data = {
                'model': meta.name,
                'result': {
                    'name': meta.name,
                    'kind': meta.kind,
                    'created': meta.created,
                    'modified': meta.modified,
                    'bucket': meta.bucket,
                }
            }
        else:
            data = {}
        return data

    def predict(self, model_id, query, payload):
        """
        Args:
            model_id (str): the name of the model
            query (dict): the query parameters
            payload (dict): the json body

        Returns:
            dict(model: id, result: dict)
        """
        data = (payload or {}).get('data')
        dataset = query.get('datax')
        if data is not None:
            columns = payload.get('columns')
            shape = payload.get('shape')
            df = pd.DataFrame(data)[columns]
            if shape is not None:
                assert len(columns) == 1, "only 1 column allowed to be reshaped"
                col = columns[0]
                df[col] = df[col].apply(lambda v: np.array(v).reshape(shape))
                df = np.stack(df[col])
            promise = self.om.runtime.model(model_id).predict(df)
        elif dataset:
            promise = self.om.runtime.model(model_id).predict(dataset)
        else:
            raise ValueError('require either "data" key in body, or ?datax=dataset')
        result = self.prepare_result(promise.get(), resource_name=model_id) if not self.is_async else promise
        return result

    def prepare_result(self, result, resource_name=None, model_id=None, raw=False, **kwargs):
        resource_name = resource_name or model_id
        result = {'model': resource_name, 'result': ensure_json_serializable(result), 'resource_uri': resource_name}
        if raw:
            result.update(result.pop('result', {}))
        return result

    def fit(self, model_id, query, payload):
        datax = query.get('datax')
        datay = query.get('datay')
        promise = self.om.runtime.model(model_id).fit(datax, datay)
        result = self.prepare_result(promise.get(), model_id=model_id) if not self.is_async else promise
        return result

    def predict_proba(self, model_id, query, payload):
        datax = query.get('datax')
        datay = query.get('datay')
        promise = self.om.runtime.model(model_id).predict_proba(datax, datay)
        result = self.prepare_result(promise.get(), model_id=model_id) if not self.is_async else promise
        return result

    def partial_fit(self, model_id, query, payload):
        datax = query.get('datax')
        datay = query.get('datay')
        promise = self.om.runtime.model(model_id).partial_fit(datax, datay)
        result = self.prepare_result(promise.get(), model_id=model_id) if not self.is_async else promise
        return result

    def score(self, model_id, query, payload):
        datax = query.get('datax')
        datay = query.get('datay')
        promise = self.om.runtime.model(model_id).score(datax, datay)
        result = self.prepare_result(promise.get(), model_id=model_id) if not self.is_async else promise
        return result

    def transform(self, model_id, query, payload):
        datax = query.get('datax')
        promise = self.om.runtime.model(model_id).transform(datax)
        result = self.prepare_result(promise.get(), model_id=model_id) if not self.is_async else promise
        return result

    def decision_function(self, model_id, query, payload):
        datax = query.get('datax')
        promise = self.om.runtime.model(model_id).decision_function(datax)
        result = self.prepare_result(promise.get(), model_id=model_id) if not self.is_async else promise
        return result

    def complete(self, model_id, query, payload):
        if model_id == '_query_':
            model_id = payload.get('model')
        raw = payload.get('raw')
        datax = payload if raw else (query.get('datax') or query.get('prompt') or payload)
        stream = True if query.get('stream') in [True, 'true', '1'] else payload.get('stream', False)
        promise = self.om.runtime.model(model_id).complete(datax, stream=stream, raw=raw)
        if stream:
            def stream_result(promise):
                class Sink(list):
                    def put(self, chunks):
                        self.extend(chunks)

                    def __bool__(self):
                        return True  # required to make work with minibatch

                buffer = Sink()
                streaming = self.om.streams.getl(f'.system/complete/{promise.id}',
                                                 executor=LocalExecutor(),
                                                 interval=0.01,
                                                 sink=buffer)
                emitter = streaming.make(lambda window: window.data)
                has_chunks = lambda: emitter.stream.buffer().limit(1).count() > 0
                while promise.state in UNREADY_STATES or has_chunks():
                    emitter.run(blocking=False)
                    for chunk in buffer:
                        yield self.prepare_result(chunk, model_id=model_id, raw=raw)
                    buffer.clear()
                    sleep(0.01)

            return stream_result(promise)
        result = self.prepare_result(promise.get(), model_id=model_id, raw=raw) if not self.is_async else promise
        return result
