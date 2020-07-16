from __future__ import absolute_import

import datetime
import glob
import os
import tempfile
import types
from shutil import rmtree
from zipfile import ZipFile, ZIP_DEFLATED

import joblib
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

        def store(result):
            if pure_python:
                result = result.tolist()
            if rName:
                meta = self.data_store.put(result, rName)
                result = meta
            return result

        result = process(maybe_chunked(model.predict,
                                       lambda data: as_args(reshaped(data)),
                                       data, **kwargs), fn=store, keep_last=True)
        return result

    def predict_proba(
          self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        data = self.data_store.get(Xname)
        model = self.model_store.get(modelname)

        def store(result):
            if pure_python:
                result = result.tolist()
            if rName:
                meta = self.data_store.put(result, rName)
                result = meta
            return result

        result = process(maybe_chunked(model.predict_proba,
                                       lambda data: as_args(reshaped(data)),
                                       data, **kwargs), fn=store, keep_last=True)

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
        process(maybe_chunked(model.partial_fit,
                              lambda X, Y: as_args(reshaped(X), reshaped(Y)),
                              X, Y, **kwargs))
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

        def store(result):
            if rName:
                meta = self.model_store.put(result, rName)
                result = meta
            return result

        result = process(maybe_chunked(model.score,
                                       lambda X, Y: as_args(reshaped(X), reshaped(Y)),
                                       X, Y, **kwargs), fn=store, keep_last=True)
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

        def store(result):
            if pure_python:
                result = result.tolist()
            if rName:
                meta = self.data_store.put(result, rName)
                result = meta
            return result

        result = process(maybe_chunked(model.fit_transform,
                                       lambda X, Y: as_args(reshaped(X), reshaped(Y)),
                                       X, Y, **kwargs), fn=store, keep_last=True)

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
        model_meta = self.model_store.put(model, modelname, attributes=model_attrs)
        return result if rName else model_meta

    def transform(self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        model = self.model_store.get(modelname)
        X = self.data_store.get(Xname)

        def store(result):
            if pure_python:
                result = result.tolist()
            if rName:
                meta = self.data_store.put(result, rName)
                result = meta
            return result

        result = process(maybe_chunked(model.transform,
                                       lambda X: as_args(reshaped(X)),
                                       X, **kwargs), fn=store, keep_last=True)
        return result

    def decision_function(self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        model = self.model_store.get(modelname)
        X = self.data_store.get(Xname)

        def store(result):
            if pure_python:
                result = result.tolist()
            if rName:
                meta = self.data_store.put(result, rName)
                result = meta
            return result

        result = process(maybe_chunked(model.decision_function,
                                       lambda X: as_args(reshaped(X)),
                                       X, **kwargs), fn=store, keep_last=True)
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


def process(it, fn=None, keep=False, keep_last=False):
    """
    consume iterator, optionally keeping results and calling a function

    Args:
        it: iterator to consume
        fn: optional, a function to call on result as result = fn(result)
        keep: optional, if True returns all results, False by default
        keep_last: optional, if True returns last result, False by default

    Returns:
        list of results if keep is True
        last result if keep_last is True
        None if keep and keep_last are False
    """
    results = [] if keep else None
    for result in it:
        result = fn(result) if fn else result
        results.append(result) if keep else None
    return result if keep_last else None


def maybe_chunked(meth, argfn, *args, **kwargs):
    """call a function with given args, kwargs, perhaps iterating over args

    Calls meth(*args, **kwargs) by the following rules:

    * if all values in *args are generators call meth() until generators exhausted
    * else run meth() once using *args as a single chunk
    * before each meth() call, argfn(*chunks) is called

    If all values in *args are generators this is equivalent to

        for values in zip(*args):
            yield meth(*values, **kwargs)

    If values in *args are not generators this is equivalent to

        yield meth(*args, **kwargs)

    Usage:
        X = get(...)
        Y = get(...)

        # original call
        model.partial_fit(X, Y, **kwargs)

        # transformed call, assuming X, Y can be generators over partial data
        # this will work whether X, Y are generators or not.
        for result in maybe_chunked(model.partial_fit,
                                    lambda *args: as_args(*args),
                                    X, Y, **kwargs):
            ... # process results as needed

        Note the (lambda ...), which is called on the X, Y args for each call
        on model.partial_fit. Use this to apply functions to each chunk, e.g.:

            # here the lambda receives the values of X, Y in each iteration
            maybe_chunked(...,
                          lambda X, Y: as_args(reshaped(X), reshaped(Y)),
                          ...)

        # combine with process() to simplify processing
        # essentiall this implements a for loop around maybe_chunked()
        resultl = process(maybe_chuncked(...), keep_last=True)

    Rationale:

        Avoid repeated code of the form

            X, Y = generators or actual values
            if isgenerator(X) and isgenerator(Y):
                for Xc, Yc in zip(X, Y):
                    chunk_result = meth(reshape(Xc), reshape(Yc), **kwargs)
                    # add logic to process chunk_result if needed
                    ...
                result = combine chunk_results, or keep only last
            else:
                result = meth(reshape(X), reshape(Y), **kwargs)

        Instead this can be written as

            result = process(maybe_chunked(meth,
                                           lambda X, Y: as_args(reshape(X), reshape(Y)),
                                           X, Y, **kwargs),
                             keep_last=True)

    Args:
        meth: function to call
        argfn: function to call on values for each iteration
        *args: arguments to meth
        **kwargs: kwargs to meth

    Returns:
        generator of meth() results
    """
    isgenerator = lambda v: isinstance(v, types.GeneratorType)
    if all(isgenerator(v) for v in args):
        for chunks in zip(*args):
            yield meth(*argfn(*chunks), **kwargs)
    else:
        yield meth(*argfn(*args), **kwargs)


def as_args(*args):
    # return the arguments as passed in
    # this is to enable e.g. lambda X: as_args(X), where X is an iterable
    # notice if we did not use as_args a subsequent fn(*(lambda X: X)) would
    # not be the same as fn(X), however fn(*(lambda X: as_args(X)) is equiv.
    return args
