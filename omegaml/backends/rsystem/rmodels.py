from omegaml.backends.basemodel import BaseModelBackend
from omegaml.runtimes.rsystem import rhelper


class RModelBackend(BaseModelBackend):
    KIND = 'model.r'

    @classmethod
    def supports(self, obj, name, **kwargs):
        return str(obj).startswith('r$')

    @property
    def r(self):
        return rhelper()

    def _package_model(self, model, key, tmpfn, **kwargs):
        modelName = model.split('$')[-1]
        self.r.om_save_model(modelName, tmpfn)
        return tmpfn

    def _extract_model(self, infile, key, tmpfn, **kwargs):
        with open(tmpfn, 'wb') as fout:
            fout.write(infile.read())
        obj = self.r.om_load_model(tmpfn, key)
        return RModelProxy(obj)

    def predict(
          self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        rmodel = self.get(modelname)
        result = rmodel.predict(Xname)
        return result


class RModelProxy:
    def __init__(self, key):
        self.key = key

    @property
    def r(self):
        return rhelper()

    def predict(self, X_or_name):
        if isinstance(X_or_name, str):
            result = self.r.om_model_predict(self, X_or_name)
        else:
            result = self.r.om_model_predict_py(self, X_or_name)
        return result
