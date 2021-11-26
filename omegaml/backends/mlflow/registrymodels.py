import os

import mlflow

from omegaml.backends.basemodel import BaseModelBackend


class MLFlowRegistryBackend(BaseModelBackend):
    """
    Backend to support registry-sourced MLFlow projects

    This supports any model tracking URI format that MLFlow supports

    Usage:
        om.scripts.put('mlflow+models://<model-name>/<runid>', '<model-name>')


    See Also
        https://www.mlflow.org/docs/latest/tracking.html
    """
    KIND = 'mlflow.registrymodel'
    MLFLOW_MODELS_PREFIX = 'mlflow+models'

    @classmethod
    def supports(self, obj, name, **kwargs):
        is_mlflow_models = isinstance(obj, str) and obj.startswith(self.MLFLOW_MODELS_PREFIX)
        return is_mlflow_models

    def put(self, obj, name, tracking_uri=None, attributes=None, **kwargs):
        """ save a MLFlow tracking-sourceable project by storing the models uri in meta.uri
        """
        models_uri = obj.replace('mlflow+models://', 'models:/')
        meta = self.data_store._make_metadata(
            name=name,
            prefix=self.data_store.prefix,
            bucket=self.data_store.bucket,
            kind=MLFlowRegistryBackend.KIND,
            uri=models_uri,
            attributes=attributes)
        self._ensure_tracking_uri(meta, tracking_uri=tracking_uri)
        return meta.save()

    def get(self, name, tracking_uri=None, **kwargs):
        """ Load MLFlow model from the tracking uri stored in metadata.uri """
        meta = self.data_store.metadata(name)
        self._ensure_tracking_uri(meta, tracking_uri=tracking_uri)
        model = mlflow.pyfunc.load_model(model_uri=f"{meta.uri}")
        return model

    def _ensure_tracking_uri(self, meta, tracking_uri=None):
        tracking_uri = (tracking_uri or mlflow.get_tracking_uri() or meta.kind_meta.get('tracking_uri') or
                        os.environ.get('MLFLOW_TRACKING_URI'))
        meta.kind_meta['tracking_uri'] = tracking_uri
        assert tracking_uri, "pass tracking_uri= or set kind_meta.tracking_uri or set env MLFLOW_TRACKING_URI"
        mlflow.tracking.MlflowClient(tracking_uri).list_registered_models(max_results=1)
        mlflow.set_tracking_uri(tracking_uri)

