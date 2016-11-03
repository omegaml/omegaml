

class BaseBackend(object):
    """
    OmegaML BaseBackend to be subclassed by other arbitrary backends
    """

    def put_model(self):
        raise NotImplementedError

    def get_model(self):
        raise NotImplementedError

    def predict(
            self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        raise NotImplementedError

    def predict_proba(
            self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        raise NotImplementedError

    def fit(self, modelname, Xname, Yname=None, pure_python=True, **kwargs):
        raise NotImplementedError

    def partial_fit(
            self, modelname, Xname, Yname=None, pure_python=True, **kwargs):
        raise NotImplementedError

    def fit_transform(
            self, modelname, Xname, Yname=None, rName=None, pure_python=True,
            **kwargs):
        raise NotImplementedError

    def transform(self, modelname, Xname, rName=None, **kwargs):
        raise NotImplementedError

    def score(
            self, modelname, Xname, Yname, rName=True, pure_python=True,
            **kwargs):
        raise NotImplementedError
