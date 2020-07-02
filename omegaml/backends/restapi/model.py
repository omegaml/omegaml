import numpy as np
import pandas as pd

from omegaml.util import ensure_json_serializable


class GenericModelResource(object):
    def __init__(self, om, is_async=False):
        self.om = om
        self.is_async = is_async

    def is_eager(self):
        return getattr(self.om.runtime.celeryapp.conf, 'CELERY_ALWAYS_EAGER', False)

    def metadata(self, request, name):
        meta = self.om.models.metadata(name)
        data = {
            'model': {
                'name': meta.name,
                'kind': meta.kind,
                'created': '{}'.format(meta.created),
                'bucket': meta.bucket,
            }
        }
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
        result = self.prepare_result(promise.get(), model_id=model_id) if not self.is_async else promise
        return result

    def prepare_result(self, result, model_id=None, **kwargs):
        return {'model': model_id, 'result': ensure_json_serializable(result)}

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


