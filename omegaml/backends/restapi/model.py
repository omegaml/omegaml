import pandas as pd
import numpy as np

from omegaml.util import ensure_json_serializable


class GenericModelResource(object):
    def __init__(self, om):
        self.om = om

    def put(self, model_id, query, payload):
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
        result = promise.get()
        # if we have a single column, get as a list
        # -- refactored from EE
        if hasattr(result, 'shape'):
            if len(result.shape) > 1 and result.shape[1] == 1:
                result = result[:, 0]
            result = result.tolist()
        return {'model': model_id, 'result': ensure_json_serializable(result)}
