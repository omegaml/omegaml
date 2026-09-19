import logging

import numpy as np
import pandas as pd

from omegaml.backends.restapi.streamable import StreamableResourceMixin
from omegaml.util import ensure_json_serializable, isTrue

logger = logging.getLogger(__name__)


class GenericModelResource(StreamableResourceMixin):
    def __init__(self, om, raw=False, stream=None, streamer=None, is_async=False, **kwargs):
        self.om = om
        self.is_async = is_async
        self.stream = stream
        self.raw = raw
        super().__init__(**kwargs)

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
                },
            }
        else:
            data = {}
        return data

    def _result_format_kwargs(self, query, payload):
        return {
            'raw': isTrue(self.raw or payload.get('raw', False) or query.get('raw')),
            'stream': isTrue(self.stream or payload.get('stream', False) or query.get('stream')),
            'streamer': self.streamer or payload.get('streamer', False) or query.get('streamer'),
        }

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
        result = self.prepare_result(promise, resource_name=model_id) if not self.is_async else promise
        return result

    def prepare_result(self, promise, resource_name=None, model_id=None, raw=False, stream=False, **kwargs):
        if stream:
            result = self.prepare_streaming_result(promise, resource_name=model_id, raw=raw)
        else:
            resource_name = resource_name or model_id
            bare_result = promise.get() if hasattr(promise, 'ready') else promise  # check for async result
            result = {
                'model': resource_name,
                'result': ensure_json_serializable(bare_result),
                'resource_uri': resource_name,
            }
            if raw:
                result.update(result.pop('result', {}))
        return result

    def fit(self, model_id, query, payload):
        datax = query.get('datax')
        datay = query.get('datay')
        promise = self.om.runtime.model(model_id).fit(datax, datay)
        result = self.prepare_result(promise, model_id=model_id) if not self.is_async else promise
        return result

    def predict_proba(self, model_id, query, payload):
        datax = query.get('datax')
        datay = query.get('datay')
        promise = self.om.runtime.model(model_id).predict_proba(datax, datay)
        result = self.prepare_result(promise, model_id=model_id) if not self.is_async else promise
        return result

    def partial_fit(self, model_id, query, payload):
        datax = query.get('datax')
        datay = query.get('datay')
        promise = self.om.runtime.model(model_id).partial_fit(datax, datay)
        result = self.prepare_result(promise, model_id=model_id) if not self.is_async else promise
        return result

    def score(self, model_id, query, payload):
        datax = query.get('datax')
        datay = query.get('datay')
        promise = self.om.runtime.model(model_id).score(datax, datay)
        result = self.prepare_result(promise, model_id=model_id) if not self.is_async else promise
        return result

    def transform(self, model_id, query, payload):
        datax = query.get('datax')
        promise = self.om.runtime.model(model_id).transform(datax)
        result = self.prepare_result(promise, model_id=model_id) if not self.is_async else promise
        return result

    def decision_function(self, model_id, query, payload):
        datax = query.get('datax')
        promise = self.om.runtime.model(model_id).decision_function(datax)
        result = self.prepare_result(promise, model_id=model_id) if not self.is_async else promise
        return result

    def complete(self, model_id, query, payload):
        model_id = self._resolve_model_id(model_id, payload)
        format_kwargs = self._result_format_kwargs(query, payload)
        datax = payload or (query.get('datax') or query.get('prompt') or payload)
        promise = self.om.runtime.model(model_id).complete(datax, **format_kwargs)
        result = self.prepare_result(promise, model_id=model_id, **format_kwargs) if not self.is_async else promise
        return result

    def embed(self, model_id, query, payload):
        model_id = self._resolve_model_id(model_id, payload)
        format_kwargs = self._result_format_kwargs(query, payload)
        datax = payload or (query.get('datax') or query.get('prompt') or payload)
        promise = self.om.runtime.model(model_id).embed(datax, **format_kwargs)
        result = self.prepare_result(promise, model_id=model_id, **format_kwargs) if not self.is_async else promise
        return result

    def transcribe(self, model_id, query, payload):
        model_id = self._resolve_model_id(model_id, payload)
        format_kwargs = self._result_format_kwargs(query, payload)
        datax = payload or (query.get('dataX') or query.get('audio') or payload)
        payload.setdefault('audio', payload.pop('files', {}).get('file'))
        promise = self.om.runtime.model(model_id).transcribe(datax, **format_kwargs)
        # TODO how do we output raw format when it is not json? prepare_result needs to handle this case
        result = self.prepare_result(promise, model_id=model_id, **format_kwargs) if not self.is_async else promise
        return result

    def speech(self, model_id, query, payload):
        model_id = self._resolve_model_id(model_id, payload)
        format_kwargs = self._result_format_kwargs(query, payload)
        datax = payload or (query.get('dataX') or query.get('input') or payload)
        promise = self.om.runtime.model(model_id).speech(datax, **format_kwargs)
        # TODO how do we output raw format when it is not json? prepare_result needs to handle this case
        result = self.prepare_result(promise, model_id=model_id, **format_kwargs) if not self.is_async else promise
        return result

    def models(self, model_id, query, payload):
        # endpoint according to https://platform.openai.com/docs/api-reference/models/
        # same code as AIPromptsView.members
        excludes = (lambda m: m.name.startswith('_'), lambda m: m.name.startswith('experiments/'))
        kind = ['genai.text', 'genai.llm']
        items = (m for m in self.om.models.list('prompts/*', kind=kind, raw=True) if not any(e(m) for e in excludes))
        models = {
            "object": "list",
            "data": [
                {
                    "id": m.name,
                    "object": "model",
                    "created": int(m.created.timestamp()),
                    "owned_by": "omegaml",
                }
                for m in items
            ],
        }
        return models

    def _resolve_model_id(self, model_id, payload):
        if model_id == '_query_':
            model_id = payload.get('model')
        return model_id
