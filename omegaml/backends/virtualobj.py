import dill
import six

from omegaml.backends.basedata import BaseDataBackend


class VirtualObjectBackend(BaseDataBackend):
    """
    Support arbitrary functions as object handlers

    Virtual object functions can be any callable that provides a __omega_virtual__
    attribute. The callable must support the following signature:

    .. code::

        @virtualobj
        def virtualobjfn(data=None, method='get|put|drop',
                         meta=None, **kwargs):
            ...
            return data

    Note that there is a distinction between storing the function as a virtual object,
    and passing data in or getting data out of the store. It is the responsibility
    of the function to implement the appropriate code for get, put, drop, as well as
    to keep track of the data it actually stores.

    As a convenience virtual object handlers can be implemented as a subclass of
    VirtualObjectHandler

    Usage:
        # create the 'foo' virtual object
        om.datasets.put(virtualobjfn, 'foo')

        # get data from the virtualobj
        om.datasets.get('foo')
        => will call virtualobjfn(method='get')

        # put data into the virtualobj
        om.datasets.put(data, 'foo')
        => will call virtualobjfn(data=data, method='put')

        # drop the virtualfn
        om.datasets.drop('name')
        => will call virtualobjfn(method='drop') and then
           drop the virtual object completely from the storage

    WARNING:

        Virtual objects are executed in the address space of the client or
        runtime context. Make sure that the source of the code is trustworthy.
        Note that this is different from Backends and Mixins as these are
        pro-actively enabled by the administrator of the client or runtime
        context, respectively - virtual objects can be injected by anyone
        who are authorized to write data.
    """
    KIND = 'virtualobj.dill'

    @classmethod
    def supports(self, obj, name, **kwargs):
        return callable(obj) and getattr(obj, '_omega_virtual', False)

    def put(self, obj, name, attributes=None, **kwargs):
        # TODO add obj signing so that only trustworthy sources can put functions
        # ensure we have a dill'able object
        # -- only instances can be dill'ed
        if isinstance(obj, six.class_types):
            obj = obj()
        data = dill.dumps(obj)
        filename = self.model_store.object_store_key(name, '.dill', hashed=True)
        gridfile = self._store_to_file(self.model_store, data, filename)
        return self.model_store._make_metadata(
            name=name,
            prefix=self.model_store.prefix,
            bucket=self.model_store.bucket,
            kind=self.KIND,
            attributes=attributes,
            gridfile=gridfile).save()

    def get(self, name, version=-1, force_python=False, lazy=False, **kwargs):
        meta = self.model_store.metadata(name)
        outf = meta.gridfile
        obj = dill.load(outf)
        outf.close()
        return obj

    def predict(self, modelname, xName, rName=None, **kwargs):
        # make this work as a model backend too
        meta = self.model_store.metadata(modelname)
        handler = self.get(modelname)
        X = self.data_store.get(xName)
        return handler(method='predict', data=X, meta=meta, store=self.model_store, rName=rName, **kwargs)

    def reduce(self, modelname, results, rName=None, **kwargs):
        """
        reduce a list of results to a single result

        Use this as the last step in a task canvas

        Args:
            modelname (str): the name of the virtualobj
            results (list): the list of results forwarded by task canvas
            rName (result): the name of the result object
            **kwargs:

        Returns:
            result of the virtualobj handler

        See Also
            om.runtime.mapreduce
        """
        meta = self.model_store.metadata(modelname)
        handler = self.get(modelname)
        return handler(method='reduce', data=results, meta=meta, store=self.model_store, rName=rName, **kwargs)


def virtualobj(fn):
    """
    function decorator to create a virtual object handler from any
    callable

    Args:
        fn: the virtual handler function

    Usage:

        .. code::

            @virtualobj
            def myvirtualobj(data=None, method=None, meta=None, store=None, **kwargs):
                ...

    See:
        VirtualObjectBackend for details on virtual object handlers

    Returns:
        fn
    """
    setattr(fn, '_omega_virtual', True)
    return fn


class VirtualObjectHandler(object):
    """
    Object-oriented API for virtual object functions
    """
    _omega_virtual = True

    def get(self, data=None, meta=None, store=None, **kwargs):
        raise NotImplementedError

    def put(self, data=None, meta=None, store=None, **kwargs):
        raise NotImplementedError

    def drop(self, data=None, meta=None, store=None, **kwargs):
        raise NotImplementedError

    def predict(self, data=None, meta=None, store=None, **kwargs):
        raise NotImplementedError

    def __call__(self, data=None, method=None, meta=None, store=None, **kwargs):
        MAP = {
            'drop': self.drop,
            'get': self.get,
            'put': self.put,
            'predict': self.predict,
        }
        methodfn = MAP[method]
        return methodfn(data=data, meta=meta, store=store, **kwargs)
