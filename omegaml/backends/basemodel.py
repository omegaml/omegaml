from pathlib import Path

import joblib
import shutil
import smart_open
import tarfile

from omegaml.backends.basecommon import BackendBaseCommon
from omegaml.util import reshaped


class BaseModelBackend(BackendBaseCommon):
    """
    OmegaML BaseModelBackend to be subclassed by other arbitrary backends

    This provides the abstract interface for any model backend to be implemented
    Subclass to implement custom backends.

    Essentially a model backend:

     * provides methods to serialize and deserialize a machine learning model for a given ML framework
     * offers fit() and predict() methods to be called by the runtime
     * offers additional methods such as score(), partial_fit(), transform()

    Model backends are the middleware that connects the om.models API to specific frameworks. This class
    makes it simple to implement a model backend by offering a common syntax as well as a default implementation
    for get() and put().

    Methods to implement:
        # for model serialization (mandatory)
        @classmethod supports() - determine if backend supports given model instance
        _package_model() - serialize a model instance into a temporary file
        _extract_model() - deserialize the model from a file-like

        By default BaseModelBackend uses joblib.dumps/loads to store the model as serialized
        Python objects. If this is not sufficient or applicable to your type models, override these
        methods.

        Both methods provide readily set up temporary file names so that all you have to do is actually
        save the model to the given output file and restore the model from the given input file, respectively.
        All other logic has already been implemented (see get_model and put_model methods).

        # for fitting and predicting (mandatory)
        fit()
        predict()

        # other methods (optional)
        fit_transform() - fit and return a transformed dataset
        partial_fit() - fit incrementally
        predict_proba() - predict probabilities
        score() - score fitted classifier vv test dataset

    """
    _backend_version_tag = '_om_backend_version'
    _backend_version = '1'

    serializer = lambda store, model, filename, **kwargs: joblib.dump(model, filename)[0]
    loader = lambda store, infile, filename=None, **kwargs: joblib.load(infile or filename)
    infer = lambda obj, **kwargs: getattr(obj, 'predict')
    reshape = lambda data, **kwargs: reshaped(data)
    types = None

    def __init__(self, model_store=None, data_store=None, tracking=None, **kwargs):
        assert model_store, "Need a model store"
        assert data_store, "Need a data store"
        self.model_store = model_store
        self.data_store = data_store
        self.tracking = tracking

    @classmethod
    def supports(self, obj, name, **kwargs):
        """
        test if this backend supports this obj
        """
        return isinstance(obj, self.types) if self.types else False

    @property
    def _call_handler(self):
        # the model store handles _pre and _post methods in self.perform()
        return self.model_store

    def get(self, name, uri=None, **kwargs):
        """
        retrieve a model

        :param name: the name of the object
        :param uri: optional, /path/to/file, defaults to meta.gridfile, may use /path/{key} as placeholder
           for the file's name
        :param version: the version of the object (not supported)

        .. versionadded: NEXT
            uri specifies a target filename to store the serialized model
        """
        # support new backend architecture while keeping back compatibility
        return self.get_model(name, uri=uri, **kwargs)

    def put(self, obj, name, uri=None, **kwargs):
        """
        store a model

        :param obj: the model object to be stored
        :param name: the name of the object
        :param uri: optional, /path/to/file, defaults to meta.gridfile, may use /path/{key} as placeholder
           for the file's name
        :param attributes: attributes for meta data

        .. versionadded: NEXT
            local specifies a local filename to store the serialized model
        """
        # support new backend architecture while keeping back compatibility
        return self.put_model(obj, name, uri=uri, **kwargs)

    def drop(self, name, force=False, version=-1, **kwargs):
        return self.model_store._drop(name, force=force, version=version)

    def _package_model(self, model, key, tmpfn, serializer=None, **kwargs):
        """
        implement this method to serialize a model to the given tmpfn

        Args:
            model (object): the model object to serialize to a file
            key (str): the object store's key for this object
            tmpfn (str): the filename to store the serialized object to
            serializer (callable): optional, a callable as serializer(store, model, filename, **kwargs),
               defaults to self.serializer, using joblib.dump()
            **kwargs (dict): optional, keyword arguments passed to the serializer

        Returns:
            tmpfn or absolute path of serialized file

        .. versionchanged:: NEXT
            enable custom serializer
        """
        serializer = serializer or getattr(self.serializer, '__func__')  # __func__ is the unbound method
        kwargs.setdefault('key', key)
        tmpfn = serializer(self, model, tmpfn, **kwargs) or tmpfn
        tmpfn = Path(tmpfn)
        fn_tgz = Path(tmpfn).parent / 's' / Path(tmpfn).name
        shutil.rmtree(fn_tgz.parent, ignore_errors=True)
        fn_tgz.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fn_tgz, 'w:') as fout:
            fout.add(tmpfn, arcname=tmpfn.relative_to(tmpfn.parent))
        return fn_tgz

    def _extract_model(self, infile, key, tmpfn, loader=None, **kwargs):
        """
        implement this method to deserialize a model from the given infile

        Args:
            infile (filelike): this is a file-like object supporting read() and seek(). if
                deserializing from this does not work directly, use tmpfn
            key (str): the object store's key for this object
            tmpfn (str): the filename from which to extract the object
            loader (callable): optional, a callable as loader(store, filename, **kwargs),
               defaults to self.loader, using joblib.load()
            **kwargs (dict): optional, keyword arguments passed to the loader

        Returns:
            model instance

        .. versionchanged:: NEXT
            enable custom loader
        """
        loader = loader or getattr(self.loader, '__func__')  # __func__ is the unbound method
        fn_tgz = Path(tmpfn).parent / 's' / Path(tmpfn).name
        fn_dir = Path(tmpfn).parent / 'x' / Path(tmpfn).name
        shutil.rmtree(fn_tgz.parent, ignore_errors=True)
        shutil.rmtree(fn_dir, ignore_errors=True)
        fn_tgz.parent.mkdir(parents=True, exist_ok=True)
        fn_dir.mkdir(parents=True, exist_ok=True)
        # -- write the tgz created by _package_model to a temp tgz file
        with open(fn_tgz, mode='wb') as fout:
            fout.write(infile.read())
        # -- extract contents, we get back what the serializer wrote
        with tarfile.open(fn_tgz, mode='r') as fin:
            fin.extractall(fn_dir)
        # call the loader
        files = list(fn_dir.glob('**/*'))
        infile = open(files[-1], 'rb') if len(files) == 1 else None
        kwargs.setdefault('key', key)
        kwargs.setdefault('filename', files[0])
        obj = loader(self, infile, **kwargs)
        infile.close() if len(files) == 1 else None
        return obj

    def _remove_path(self, path):
        """
        Remove a path, either a file or a directory

        Args:
            path (str): filename or path to remove. If path is a directory,
            it will be removed recursively. If path is a file, it will be
            removed.

        Returns:
            None
        """
        if Path(path).is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            Path(path).unlink(missing_ok=True)

    def get_model(self, name, version=-1, uri=None, loader=None, **kwargs):
        """
        Retrieves a pre-stored model
        """
        meta = self.model_store.metadata(name)
        storekey = self.model_store.object_store_key(name, 'omm', hashed=True)
        uri = uri or meta.uri
        if uri:
            uri = str(uri).format(key=storekey)
            infile = smart_open.open(uri, 'rb')
        else:
            infile = meta.gridfile
        model = self._extract_model(infile, storekey,
                                    self._tmp_packagefn(self.model_store, storekey),
                                    loader=loader, **kwargs)
        infile.close()
        return model

    def put_model(self, obj, name, attributes=None, _kind_version=None, uri=None, **kwargs):
        """
        Packages a model using joblib and stores in GridFS
        """
        storekey = self.model_store.object_store_key(name, 'omm', hashed=True)
        tmpfn = self._tmp_packagefn(self.model_store, storekey)
        packagefname = self._package_model(obj, storekey, tmpfn, **kwargs) or tmpfn
        gridfile = self._store_to_file(self.model_store, packagefname, storekey, uri=uri)
        self._remove_path(packagefname)
        kind_meta = {
            self._backend_version_tag: self._backend_version,
        }
        return self.model_store._make_metadata(
            name=name,
            prefix=self.model_store.prefix,
            bucket=self.model_store.bucket,
            kind=self.KIND,
            kind_meta=kind_meta,
            attributes=attributes,
            uri=str(uri or ''),
            gridfile=gridfile).save()

    def predict(
            self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        """
        predict using data stored in Xname

        :param modelname: the name of the model object
        :param Xname: the name of the X data set
        :param rName: the name of the result data object or None
        :param pure_python: if True return a python object. If False return
            a dataframe. Defaults to True to support any client.
        :param kwargs: kwargs passed to the model's predict method
        :return: return the predicted outcome
        """
        model = self.model_store.get(modelname)
        data = self._resolve_input_data('predict', Xname, 'X', **kwargs)
        infer = getattr(self.infer, '__func__')  # __func__ is the unbound method
        reshape = getattr(self.reshape, '__func__')
        result = infer(model)(reshape(data))
        return self._prepare_result('predict', result, rName=rName,
                                    pure_python=pure_python, **kwargs)

    def _resolve_input_data(self, method, Xname, key, **kwargs):
        data = self.data_store.get(Xname)
        meta = self.data_store.metadata(Xname)
        if self.tracking and getattr(self.tracking, 'autotrack', False):
            self.tracking.log_data(key, data, dataset=Xname, kind=meta.kind, event=method)
        return data

    def _prepare_result(self, method, result, rName=None, pure_python=False, **kwargs):
        if pure_python:
            result = result.tolist()
        if rName:
            meta = self.data_store.put(result, rName)
            result = meta
        if self.tracking and getattr(self.tracking, 'autotrack', False):
            self.tracking.log_data('Y', result, dataset=rName, kind=str(type(result)) if rName is None else meta.kind,
                                   event=method)
        return result

    def predict_proba(
            self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        """
        predict the probability using data stored in Xname

        :param modelname: the name of the model object
        :param Xname: the name of the X data set
        :param rName: the name of the result data object or None
        :param pure_python: if True return a python object. If False return
            a dataframe. Defaults to True to support any client.
        :param kwargs: kwargs passed to the model's predict method
        :return: return the predicted outcome
        """
        raise NotImplementedError

    def fit(self, modelname, Xname, Yname=None, pure_python=True, **kwargs):
        """
        fit the model with data

        :param modelname: the name of the model object
        :param Xname: the name of the X data set
        :param Yname: the name of the Y data set
        :param pure_python: if True return a python object. If False return
           a dataframe. Defaults to True to support any client.
        :param kwargs: kwargs passed to the model's predict method
        :return: return the meta data object of the model
        """
        raise NotImplementedError

    def partial_fit(
            self, modelname, Xname, Yname=None, pure_python=True, **kwargs):
        """
        partially fit the model with data (online)

        :param modelname: the name of the model object
        :param Xname: the name of the X data set
        :param Yname: the name of the Y data set
        :param pure_python: if True return a python object. If False return
           a dataframe. Defaults to True to support any client.
        :param kwargs: kwargs passed to the model's predict method
        :return: return the meta data object of the model
        """

        raise NotImplementedError

    def fit_transform(
            self, modelname, Xname, Yname=None, rName=None, pure_python=True,
            **kwargs):
        """
        fit and transform using data

        :param modelname: the name of the model object
        :param Xname: the name of the X data set
        :param Yname: the name of the Y data set
        :param rName: the name of the transforms's result data object or None
        :param pure_python: if True return a python object. If False return
           a dataframe. Defaults to True to support any client.
        :param kwargs: kwargs passed to the model's transform method
        :return: return the meta data object of the model
        """
        raise NotImplementedError

    def transform(self, modelname, Xname, rName=None, **kwargs):
        """
        transform using data

        :param modelname: the name of the model object
        :param Xname: the name of the X data set
        :param rName: the name of the transforms's result data object or None
        :param kwargs: kwargs passed to the model's transform method
        :return: return the transform data of the model
        """
        raise NotImplementedError

    def score(
            self, modelname, Xname, Yname=None, rName=True, pure_python=True,
            **kwargs):
        """
        score using data

        :param modelname: the name of the model object
        :param Xname: the name of the X data set
        :param Yname: the name of the Y data set
        :param rName: the name of the transforms's result data object or None
        :param pure_python: if True return a python object. If False return
           a dataframe. Defaults to True to support any client.
        :param kwargs: kwargs passed to the model's predict method
        :return: return the score result
        """
        raise NotImplementedError
