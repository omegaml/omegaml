

from __future__ import absolute_import
import tempfile
import glob
import os
from mongoengine.fields import GridFSProxy
from .base import BaseBackend
from zipfile import ZipFile, ZIP_DEFLATED
from shutil import rmtree


class ScikitLearnBackend(BaseBackend):
    """
    OmegaML backend to use with ScikitLearn
    """
    def __init__(self, store):
        self.store = store

    def _package_model(self, model, filename):
        """
        Dumps a model using joblib and packages all of joblib files into a zip
        file
        """
        import joblib
        lpath = tempfile.mkdtemp()
        fname = os.path.basename(filename)
        mklfname = os.path.join(lpath, fname)
        zipfname = os.path.join(self.store.tmppath, fname)
        joblib.dump(model, mklfname)
        with ZipFile(zipfname, 'w', compression=ZIP_DEFLATED) as zipf:
            for part in glob.glob(os.path.join(lpath, '*')):
                zipf.write(part, os.path.basename(part))
        rmtree(lpath)
        return zipfname

    def _extract_model(self, packagefname):
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

    def get_model(self, name, version=-1):
        """
        Retrieves a pre-stored model
        """
        filename = self.store._get_obj_store_key(name, '.omm')
        packagefname = os.path.join(self.store.tmppath, name)
        dirname = os.path.dirname(packagefname)
        try:
            os.makedirs(dirname)
        except OSError:
            # OSError is raised if path exists already
            pass
        outf = self.store.fs.get_version(filename, version=version)
        with open(packagefname, 'w') as zipf:
            zipf.write(outf.read())
        model = self._extract_model(packagefname)
        return model

    def put_model(self, obj, name, attributes=None):
        """
        Packages a model using joblib and stores in GridFS
        """
        from ..documents import Metadata
        zipfname = self._package_model(obj, name)
        with open(zipfname) as fzip:
            fileid = self.store.fs.put(
                fzip, filename=self.store._get_obj_store_key(name, 'omm'))
            gridfile = GridFSProxy(grid_id=fileid,
                                   db_alias='omega',
                                   collection_name=self.store.bucket)
        return self.store._make_metadata(
            name=name,
            prefix=self.store.prefix,
            bucket=self.store.bucket,
            kind=Metadata.SKLEARN_JOBLIB,
            attributes=attributes,
            gridfile=gridfile).save()

    def predict(
            self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        from omegaml import Omega
        om = Omega()
        data, meta = om.get_data(Xname)
        model = self.get_model(modelname)
        result = model.predict(data, **kwargs)
        if pure_python:
            result = result.tolist()
        if rName:
            meta = self.put_model(result, rName)
            result = meta
        return result

    def predict_proba(
            self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        from omegaml import Omega
        om = Omega()
        data, meta = om.get_data(Xname)
        model = self.get_model(modelname)
        result = model.predict_proba(data, **kwargs)
        if pure_python:
            result = result.tolist()
        if rName:
            om.put(result, rName)
            result = meta
        return result

    def fit(self, modelname, Xname, Yname=None, pure_python=True, **kwargs):
        from omegaml import Omega
        om = Omega()
        model = self.get_model(modelname)
        X, metaX = om.get_data(Xname)
        Y, metaY = None, None
        if Yname:
            Y, metaY = om.get_data(Yname)
        result = model.fit(X, Y, **kwargs)
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
        om.models.put(model, modelname, attributes=model_attrs)
        if pure_python:
            result = '%s' % result

    def partial_fit(
            self, modelname, Xname, Yname=None, pure_python=True, **kwargs):
        from omegaml import Omega
        om = Omega()
        model = self.get_model(modelname)
        X, metaX = om.get_data(Xname)
        Y, metaY = None, None
        if Yname:
            Y, metaY = om.get_data(Yname)
        result = model.partial_fit(X, Y, **kwargs)
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
        om.models.put(model, modelname, attributes=model_attrs)
        if pure_python:
            result = '%s' % result
        return result

    def score(
            self, modelname, Xname, Yname, rName=True, pure_python=True,
            **kwargs):
        from omegaml import Omega
        om = Omega()
        model = self.get_model(modelname)
        X, _ = om.get_data(Xname)
        Y, _ = om.get_data(Yname)
        result = model.score(X, Y, **kwargs)
        if rName:
            meta = om.put(result, rName)
            result = meta
        return result

    def fit_transform(
            self, modelname, Xname, Yname=None, rName=None, pure_python=True,
            **kwargs):
        from omegaml import Omega
        om = Omega()
        model = self.get_model(modelname)
        X, metaX = om.get_data(Xname)
        Y, metaY = None, None
        if Yname:
            Y, metaY = om.get_data(Yname)
        result = model.fit_transform(X, Y, **kwargs)
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
        om.models.put(model, modelname, attributes=model_attrs)
        if rName:
            om.put(result, rName)
        return result

    def transform(self, modelname, Xname, rName=None, **kwargs):
        from omegaml import Omega
        om = Omega()
        model = self.get_model(modelname)
        X, _ = om.get_data(Xname)
        result = model.transform(X, **kwargs)
        if rName:
            meta = om.put(result, rName)
            result = meta
        return result
