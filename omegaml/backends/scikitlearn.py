from __future__ import absolute_import

import glob
from zipfile import ZipFile, ZIP_DEFLATED

import datetime
import joblib
import os
import tempfile
from shutil import rmtree
from sklearn.base import BaseEstimator
from sklearn.model_selection import GridSearchCV

from omegaml.backends.basemodel import BaseModelBackend
from omegaml.documents import MDREGISTRY
from omegaml.util import reshaped, gsreshaped

# byte string
_u8 = lambda t: t.encode('UTF-8', 'replace') if isinstance(t, str) else t

class ScikitLearnBackendV1(BaseModelBackend):
    KIND = MDREGISTRY.SKLEARN_JOBLIB

    @classmethod
    def supports(self, obj, name, **kwargs):
        return isinstance(obj, BaseEstimator)

    # kept to support legacy scikit learn model serializations prior to ~scikit learn v0.18
    def _v1_package_model(self, model, filename):
        """
        Dumps a model using joblib and packages all of joblib files into a zip
        file
        """
        import joblib
        lpath = tempfile.mkdtemp()
        fname = os.path.basename(filename)
        mklfname = os.path.join(lpath, fname)
        zipfname = os.path.join(self.model_store.tmppath, fname)
        joblib.dump(model, mklfname, protocol=4)
        with ZipFile(zipfname, 'w', compression=ZIP_DEFLATED) as zipf:
            for part in glob.glob(os.path.join(lpath, '*')):
                zipf.write(part, os.path.basename(part))
        rmtree(lpath)
        return zipfname

    def _v1_extract_model(self, packagefname):
        """
        Loads a model using joblib from a zip file created with _package_model
        """
        import joblib
        lpath = tempfile.mkdtemp()
        fname = os.path.basename(packagefname)
        mklfname = os.path.join(lpath, fname)
        with ZipFile(packagefname) as zipf:
            zipf.extractall(lpath)
        model = joblib.load(mklfname)
        rmtree(lpath)
        return model

    def _v1_get_model(self, name, version=-1):
        """
        Retrieves a pre-stored model
        """
        filename = self.model_store._get_obj_store_key(name, '.omm')
        packagefname = os.path.join(self.model_store.tmppath, name)
        dirname = os.path.dirname(packagefname)
        try:
            os.makedirs(dirname)
        except OSError:
            # OSError is raised if path exists already
            pass
        meta = self.model_store.metadata(name, version=version)
        outf = self.model_store.fs.get_version(filename, version=version)
        with open(packagefname, 'wb') as zipf:
            zipf.write(meta.gridfile.read())
        model = self._v1_extract_model(packagefname)
        return model

    def _v1_put_model(self, obj, name, attributes=None):
        """
        Packages a model using joblib and stores in GridFS
        """
        zipfname = self._v1_package_model(obj, name)
        with open(zipfname, 'rb') as fzip:
            gridfile = self.model_store.fs.put(
                fzip, filename=self.model_store._get_obj_store_key(name, 'omm'))
        return self.model_store._make_metadata(
            name=name,
            prefix=self.model_store.prefix,
            bucket=self.model_store.bucket,
            kind=MDREGISTRY.SKLEARN_JOBLIB,
            attributes=attributes,
            gridfile=gridfile).save()


class ScikitLearnBackendV2(ScikitLearnBackendV1):
    """
    OmegaML backend to use with ScikitLearn
    """
    def _package_model(self, model, key, tmpfn):
        """
        Dumps a model using joblib and packages all of joblib files into a zip
        file
        """
        joblib.dump(model, tmpfn, protocol=4, compress=True)
        return tmpfn

    def _extract_model(self, infile, key, tmpfn):
        """
        Loads a model using joblib from a zip file created with _package_model
        """
        with open(tmpfn, 'wb') as pkgf:
            pkgf.write(infile.read())
        model = joblib.load(tmpfn)
        return model

    def get_model(self, name, version=-1):
        """
        Retrieves a pre-stored model
        """
        meta = self.model_store.metadata(name)
        if self._backend_version != meta.kind_meta.get(self._backend_version_tag):
            return super()._v1_get_model(name, version=version)
        return super().get_model(name, version=version)

    def put_model(self, obj, name, attributes=None, _kind_version=None):
        if _kind_version and _kind_version != self._backend_version:
            return super()._v1_put_model(obj, name, attributes=attributes)
        return super().put_model(obj, name, attributes=attributes)

    def predict(
          self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        data = self.data_store.get(Xname)
        model = self.model_store.get(modelname)
        result = model.predict(reshaped(data), **kwargs)
        if pure_python:
            result = result.tolist()
        if rName:
            meta = self.data_store.put(result, rName)
            result = meta
        return result

    def predict_proba(
          self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        data = self.data_store.get(Xname)
        model = self.model_store.get(modelname)
        result = model.predict_proba(reshaped(data), **kwargs)
        if pure_python:
            result = result.tolist()
        if rName:
            meta = self.data_store.put(result, rName)
            result = meta
        return result

    def fit(self, modelname, Xname, Yname=None, pure_python=True, **kwargs):
        model = self.model_store.get(modelname)
        X, metaX = self.data_store.get(Xname), self.data_store.metadata(Xname)
        Y, metaY = None, None
        if Yname:
            Y, metaY = (self.data_store.get(Yname),
                        self.data_store.metadata(Yname))
        model.fit(reshaped(X), reshaped(Y), **kwargs)
        # store information required for retraining
        model_attrs = {
            'metaX': metaX.to_mongo(),
            'metaY': metaY.to_mongo() if metaY is not None else None,
        }
        try:
            import sklearn
            model_attrs['scikit-learn'] = sklearn.__version__
        except:
            model_attrs['scikit-learn'] = 'unknown'
        meta = self.model_store.put(model, modelname, attributes=model_attrs)
        return meta

    def partial_fit(
          self, modelname, Xname, Yname=None, pure_python=True, **kwargs):
        model = self.model_store.get(modelname)
        X, metaX = self.data_store.get(Xname), self.data_store.metadata(Xname)
        Y, metaY = None, None
        if Yname:
            Y, metaY = (self.data_store.get(Yname),
                        self.data_store.metadata(Yname))
        model.partial_fit(reshaped(X), reshaped(Y), **kwargs)
        # store information required for retraining
        model_attrs = {
            'metaX': metaX.to_mongo(),
            'metaY': metaY.to_mongo() if metaY is not None else None,
        }
        try:
            import sklearn
            model_attrs['scikit-learn'] = sklearn.__version__
        except:
            model_attrs['scikit-learn'] = 'unknown'
        meta = self.model_store.put(model, modelname, attributes=model_attrs)
        return meta

    def score(
          self, modelname, Xname, Yname=None, rName=None, pure_python=True,
          **kwargs):
        model = self.model_store.get(modelname)
        X = self.data_store.get(Xname)
        Y = self.data_store.get(Yname)
        result = model.score(reshaped(X), reshaped(Y), **kwargs)
        if rName:
            meta = self.model_store.put(result, rName)
            result = meta
        return result

    def fit_transform(
          self, modelname, Xname, Yname=None, rName=None, pure_python=True,
          **kwargs):
        model = self.model_store.get(modelname)
        X, metaX = self.data_store.get(Xname), self.data_store.metadata(Xname)
        Y, metaY = None, None
        if Yname:
            Y, metaY = (self.data_store.get(Yname),
                        self.data_store.metadata(Yname))
        result = model.fit_transform(reshaped(X), reshaped(Y), **kwargs)
        # store information required for retraining
        model_attrs = {
            'metaX': metaX.to_mongo(),
            'metaY': metaY.to_mongo() if metaY is not None else None
        }
        try:
            import sklearn
            model_attrs['scikit-learn'] = sklearn.__version__
        except:
            model_attrs['scikit-learn'] = 'unknown'
        meta = self.model_store.put(model, modelname, attributes=model_attrs)
        if pure_python:
            result = result.tolist()
        if rName:
            meta = self.data_store.put(result, rName)
        result = meta
        return result

    def transform(self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        model = self.model_store.get(modelname)
        X = self.data_store.get(Xname)
        result = model.transform(reshaped(X), **kwargs)
        if pure_python:
            result = result.tolist()
        if rName:
            meta = self.data_store.put(result, rName)
            result = meta
        return result

    def decision_function(self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        model = self.model_store.get(modelname)
        X = self.data_store.get(Xname)
        result = model.decision_function(reshaped(X), **kwargs)
        if pure_python:
            result = result.tolist()
        if rName:
            meta = self.data_store.put(result, rName)
            result = meta
        return result

    def gridsearch(self, modelname, Xname, Yname, rName=None,
                   parameters=None, pure_python=True, **kwargs):
        model, meta = self.model_store.get(modelname), self.model_store.metadata(modelname)
        X = self.data_store.get(Xname)
        if Yname:
            y = self.data_store.get(Yname)
        else:
            y = None
        gs_model = GridSearchCV(cv=5, estimator=model, param_grid=parameters, **kwargs)
        gs_model.fit(X, gsreshaped(y))
        nowdt = datetime.datetime.now()
        if rName:
            gs_modelname = rName
        else:
            gs_modelname = '{}.{}.gs'.format(modelname, nowdt.isoformat())
        gs_meta = self.model_store.put(gs_model, gs_modelname)
        attributes = meta.attributes
        if not 'gridsearch' in attributes:
            attributes['gridsearch'] = []
        attributes['gridsearch'].append({
            'datetime': nowdt,
            'Xname': Xname,
            'Yname': Yname,
            'gsModel': gs_modelname,
        })
        meta.save()
        return meta


class ScikitLearnBackend(ScikitLearnBackendV2):
    pass
