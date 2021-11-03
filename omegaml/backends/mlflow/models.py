import glob

import mlflow
import os
from tarfile import TarFile

from omegaml.backends.basemodel import BaseModelBackend


class MLFlowModelBackend(BaseModelBackend):
    """ A backend for mlflow models

    This provides storage support for mlflow models. The following
    semantics are supported:

    * mlflow storage format: directories with a MLmodel spec file
    * any of the mlflow-supported frameworks
    * mlflow.models.Model: mlflow custom models of any flavor
    * mlflow.pyfunc.PythonModel:  mlflow Python models of any flavor

    For mlflow storage format, the backend creates a tar file and stores
    it as a blob object.

    For any mlflow-supported frameworks, the backend infers the model
    format and uses the corresponding mlflow.<flavor>.save_model() method

    For mlflow.models.Model instances, the backend uses Model.save() to
    save the model

    For mlflow.pyfunc.PythonModel, the backend uses pyfunc.save_model() to
    save the model

    On loading the model, the backend invariable uses mlflow.pyfunc.load_model()
    to load it back.

    Usage:
        1) Use case: deploy a mlflow model

            # in mlflow save some model
            mlflow.save_model(model, "/path/to/mymodel")
            # deploy using omega-ml
            om.models.put("/path/to/mymodel", 'mymodel')

        2) Use case: deploy a PythonModel

            # mymodel.py
            class MyModel(mlflow.pyfunc.PythonModel):
                def predict(context, data):
                    ...

            model = MyModel()
            om.models.put(model, 'mymodel')

        3) Use case: deploy any mlflow-supported flavor

            model = SomeModel()
            om.models.put(model, 'mymodel')

        Once the model is saved in om.models, it can be used by
        om.runtime.model() as well as throught the REST API as any
        other model.
    """
    KIND = 'mlflow.model'
    MLFLOW_TYPES = (mlflow.models.Model, mlflow.pyfunc.PythonModel)
    MLFLOW_PREFIX = 'mlflow://'

    @classmethod
    def supports(cls, obj, name, **kwargs):
        if str(obj).startswith(cls.MLFLOW_PREFIX):
            obj = obj.replace(cls.MLFLOW_PREFIX, '')
        is_mlflow_type = isinstance(obj, cls.MLFLOW_TYPES)
        is_mlflow_mlfile = isinstance(obj, str) and obj.lower().endswith('mlmodel') and cls._is_path(cls, obj)
        is_mlflow_modelpath = isinstance(obj, str) and cls._is_path(cls, os.path.join(obj, 'MLmodel'))
        kind_requested = kwargs.get('kind') == cls.KIND
        is_mlflow_flavor = cls._infer_model_flavor(cls, obj)
        return is_mlflow_type or is_mlflow_mlfile or is_mlflow_modelpath or kind_requested or is_mlflow_flavor

    def _infer_model_flavor(self, model):
        from google.protobuf.message import Message
        model_type = type(model).__module__
        model_flavor = model_type.split('.', 1)[0]
        flavor_supported = model_flavor in mlflow._model_flavors_supported
        non_models = (
            lambda m: isinstance(m, Message),
        )
        not_a_model = any(test(model) for test in non_models)
        return not not_a_model and flavor_supported and getattr(mlflow, model_flavor, None)

    def _package_model(self, model, key, tmpfn, **kwargs):
        # package the model using corresponding save or save_model method
        model_path = os.path.join(self.model_store.tmppath, key + '.mlflow')
        if isinstance(model, mlflow.models.Model):
            model.save(model, tmpfn)
        elif isinstance(model, mlflow.pyfunc.PythonModel):
            mlflow.pyfunc.save_model(model_path, python_model=model,
                                     artifacts=kwargs.get('artifacts'))
        elif isinstance(model, str) and (self._is_path(model)
                                         or model.startswith(self.MLFLOW_PREFIX)):
            # a mlflow model local storage
            # https://www.mlflow.org/docs/latest/models.html#storage-format
            if model.startswith(self.MLFLOW_PREFIX):
                model = model.replace(self.MLFLOW_PREFIX, '')
            if model.lower().endswith('mlmodel'):
                model_path = os.path.dirname(model)
            else:
                model_path = model
        else:
            # some supported model flavor perhaps?
            flavor = self._infer_model_flavor(model)
            flavor.save_model(model, model_path, **kwargs)
        with TarFile(tmpfn, mode='w') as tarf:
            tarf.add(model_path, recursive=True)
        return tmpfn

    def _extract_model(self, infile, key, tmpfn, **kwargs):
        model_path = os.path.join(self.model_store.tmppath, key + '.mlflow')
        with open(tmpfn, 'wb') as fout:
            fout.write(infile.read())
        with TarFile(tmpfn, mode='r') as tarf:
            tarf.extractall(model_path)
        for fn in glob.glob(f'{model_path}/**/MLmodel', recursive=True):
            model = mlflow.pyfunc.load_model(os.path.dirname(fn))
            break
        return model
