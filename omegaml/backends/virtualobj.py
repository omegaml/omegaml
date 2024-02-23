import builtins
import dill
import sys
import types
import warnings

from omegaml.backends.basedata import BaseDataBackend
from omegaml.util import tryOr


class VirtualObjectBackend(BaseDataBackend):
    """
    Support arbitrary functions as object handlers

    Virtual object functions can be any callable that provides a __omega_virtual__
    attribute. The callable must support the following signature::

        @virtualobj
        def virtualobjfn(data=None, method='get|put|drop',
                         meta=None, store=None, **kwargs):
            ...
            return data

    Note that there is a distinction between storing the function as a virtual object,
    and passing data in or getting data out of the store. It is the responsibility
    of the function to implement the appropriate code for get, put, drop, as well as
    to keep track of the data it actually stores.

    As a convenience virtual object handlers can be implemented as a subclass of
    VirtualObjectHandler

    Usage::

        1) as a virtual data handler

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

        2) as a virtual model

            # create the mymodel model as a virtualobj
            om.models.put(virtualobjfn, 'mymodel')

            # run the model's predict() function
            om.runtime.model('mymodel').predict(X)
            => will call virtualobjfn(method='predict')

        3) as a virtual script

            # create the myscript script as a virtualobj
            om.models.put(virtualobjfn, 'myscript')

            # run the script
            om.runtime.script('myscript').run()
            => will call virtualobjfn(method='run')

    WARNING:

        Virtual objects are executed in the address space of the client or
        runtime context. Make sure that the source of the code is trustworthy.
        Note that this is different from Backends and Mixins as these are
        pro-actively enabled by the administrator of the client or runtime
        context, respectively - virtual objects can be injected by anyone
        who are authorized to write data.
    """
    # TODO split VirtualObjectBackend into VirtualModelBackend and VirtualDataBackend
    #      to avoid confusion between the two (currently the same class is used for both)
    KIND = 'virtualobj.dill'
    PROMOTE = 'export'

    @classmethod
    def supports(self, obj, name, **kwargs):
        return callable(obj) and getattr(obj, '_omega_virtual', False)

    @property
    def _call_handler(self):
        # the model store handles _pre and _post methods in self.perform()
        return self.model_store

    def put(self, obj, name, attributes=None, dill_kwargs=None, as_source=False, **kwargs):
        # TODO add obj signing so that only trustworthy sources can put functions
        # since 0.15.6: only __main__ objects are stored as bytecodes,
        #               all module code is stored as source code. This
        #               removes the dependency on opcode parity between client
        #               and server. Source objects are compiled into __main__
        #               within the runtime. This is a tradeoff compatibility
        #               v.s. execution time. Use as_source=False to force
        #               storing bytecodes.
        data = dilldip.dumps(obj, as_source=as_source, **(dill_kwargs or {}))
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
        data = outf.read()
        obj = dilldip.loads(data)
        outf.close()
        return obj

    def _ensure_handler_instance(self, obj):
        # ensure VirtualObjectHandler classes are transformed to a virtualobj
        return obj() if isinstance(obj, type) and issubclass(obj, VirtualObjectHandler) else obj

    def predict(self, modelname, xName, rName=None, **kwargs):
        # make this work as a model backend too
        meta = self.model_store.metadata(modelname)
        handler = self._ensure_handler_instance(self.get(modelname))
        X = self.data_store.get(xName)
        return handler(method='predict', data=X, meta=meta, store=self.model_store, rName=rName,
                       tracking=self.tracking, **kwargs)

    def fit(self, modelname, xName, yName=None, rName=None, **kwargs):
        # make this work as a model backend too
        meta = self.model_store.metadata(modelname)
        handler = self._ensure_handler_instance(self.get(modelname))
        X = self.data_store.get(xName)
        y = self.data_store.get(yName) if yName else None
        return handler(method='fit', data=(X, y), meta=meta, store=self.model_store, rName=rName,
                       tracking=self.tracking, **kwargs)

    def score(self, modelname, xName, yName=None, rName=None, **kwargs):
        # make this work as a model backend too
        meta = self.model_store.metadata(modelname)
        handler = self._ensure_handler_instance(self.get(modelname))
        X = self.data_store.get(xName)
        y = self.data_store.get(yName) if yName else None
        return handler(method='score', data=(X, y), meta=meta, store=self.model_store, rName=rName,
                       tracking=self.tracking, **kwargs)

    def run(self, scriptname, *args, **kwargs):
        # run as a script
        meta = self.model_store.metadata(scriptname)
        handler = self._ensure_handler_instance(self.get(scriptname))
        data = args[0] if args else None
        kwargs['args'] = args
        return handler(method='run', data=data, meta=meta, store=self.data_store, tracking=self.tracking, **kwargs)

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
        handler = self._ensure_handler_instance(self.get(modelname))
        return handler(method='reduce', data=results, meta=meta, store=self.model_store, rName=rName,
                       tracking=self.tracking, **kwargs)


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

    def run(self, data=None, meta=None, store=None, **kwargs):
        raise NotImplementedError

    def __call__(self, data=None, method=None, meta=None, store=None, tracking=None, **kwargs):
        MAP = {
            'drop': self.drop,
            'get': self.get,
            'put': self.put,
            'predict': self.predict,
            'run': self.run,
        }
        methodfn = MAP[method]
        return methodfn(data=data, meta=meta, store=store, tracking=tracking, **kwargs)


class _DillDip:
    # magic id for dipped dill objects
    # -- why 0x1565? 15g of dill dip have 65 kcal
    # -- see https://www.nutritionvalue.org/Dill_dip%2C_regular_12350210_nutritional_value.html
    # -- also 42 is overused
    __calories = 0x1565

    # enhanced dill for functions and classes
    # - warns about bound variables that could cause issues when undilling
    # - checks types and functions are defined in __main__ before dilling (so we will code, not references),
    #   dynamically recompiles in __main__ before dilling if source is available
    # - saves source code for improved python cross-version compatibility
    # - falls back on standard dill for any other object type
    def dumps(self, obj, as_source=False, **dill_kwargs):
        # enhanced flavor of dill that stores source code for cross-version compatibility
        # ensure we have a dill'able object
        # if isinstance(obj, type):
        #    obj = obj()
        self._check(obj)
        data = (self._dill_main(obj, **dill_kwargs) or
                self._dill_types_or_function(obj, as_source=as_source, **dill_kwargs) or
                self._dill_dill(obj, **dill_kwargs))
        return data

    def loads(self, data):
        # compat: Python 3.8.x < 3.8.2
        # https://github.com/python/cpython/commit/b19f7ecfa3adc6ba1544225317b9473649815b38
        # https://docs.python.org/3.8/whatsnew/changelog.html#python-3-8-2-final
        try:
            obj = self._dynamic_compile(dill.loads(data), module='__main__')
        except ModuleNotFoundError as e:
            # if the functions original module is not known, simulate it
            # this is to deal with functions created outside of __main__
            # see https://stackoverflow.com/q/26193102/890242
            #     https://stackoverflow.com/a/70513630/890242
            mod = types.ModuleType(e.name, '__dynamic__')
            sys.modules[e.name] = mod  # sys.modules['__main__']
            obj = dill.loads(data)
        return obj

    def _check(self, obj):
        # check for freevars
        freevars = dill.detect.nestedglobals(obj)
        freevars += list(dill.detect.freevars(obj).keys())
        freevars += list(dill.detect.referredglobals(obj))
        freevars = [n for n in set(freevars) if n not in dir(builtins)]
        if len(freevars):
            warnings.warn(
                f'The {repr(obj)} module references {freevars}, this may lead to errors at runtime; import/declare all variables within method/function scope')

    def _dill_dill(self, obj, **dill_kwargs):
        # fallback to standard dill
        # e.g. class instances cannot be dumped unless they come from __main__
        return dill.dumps(obj, **dill_kwargs)

    def _dill_main(self, obj, **dill_kwargs):
        # dynamic __main__ objects can be dilled directly, there is no source code
        if dill.source.isfrommain(obj) or dill.source.isdynamic(obj):
            return dill.dumps(obj, **dill_kwargs)
        return None

    def _dill_types_or_function(self, obj, as_source=False, **dill_kwargs):
        # classes or functions should be dilled as source, unless they come from __main__
        if isinstance(obj, type) or isinstance(obj, types.FunctionType):
            return self._dill_source(obj, as_source=as_source, **dill_kwargs)
        return None

    def _dill_source(self, obj, as_source=False, **dill_kwargs):
        # include source code along dill
        try:
            source = dill.source.getsource(obj, lstrip=True)
            source_obj = {'__dipped__': self.__calories,
                          'source': ''.join(source),
                          'name': getattr(obj, '__name__'),
                          '__dict__': getattr(obj, '__dict__', {})}
        except:
            source_obj = {}
        else:
            # check obvious references in source
            if '__main__' in source_obj.get('source', []):
                warnings.warn(f'The {repr(obj)} references __main__, this may lead to unexpected results')
        if as_source and source_obj:
            # if source code was requested, transport as source code
            data = dill.dumps(source_obj, **dill_kwargs)
        elif source_obj and dill.detect.getmodule(obj) != '__main__':
            # we have a source obj, make sure we can dill it and have source to revert from
            # compile to __main__ module to enable full serialization
            warnings.warn(f'The {repr(obj)} is defined outside of __main__, recompiling in __main__.')
            obj = self._dynamic_compile(source_obj, module='__main__')
            source_obj['dill'] = dill.dumps(obj, **dill_kwargs)
            data = dill.dumps(source_obj, **dill_kwargs)
        else:
            # we have no source object, revert to standard dill
            if as_source:
                warnings.warn(f'Cannot save {repr(obj)} as source code, reverting to dill')
            # could not get source code, revert to dill
            data = dill.dumps(obj, **dill_kwargs)
        return data

    def _dynamic_compile(self, obj, module='__main__'):
        # re-compile source obj in __main__
        if self.isdipped(obj):
            if 'dill' in obj:
                try:
                    obj = dill.loads(obj['dill'])
                except:
                    warnings.warn('could not undill, reverting to dynamic compile source code')
                else:
                    return obj
            source, data = obj.get('source'), obj.get('__dict__', {})
            mod = types.ModuleType(module)
            mod.__dict__.update({'__compiling__': True,
                                 'virtualobj': virtualobj,
                                 'VirtualObjectHandler': VirtualObjectHandler})
            sys.modules[module] = mod
            code = compile(source, '<string>', 'exec')
            exec(code, mod.__dict__)
            obj = getattr(mod, obj['name'])
            # restore instance data, if any
            try:
                getattr(obj, '__dict__', {}).update(data)
            except AttributeError:
                # we ignore attribute errors on class types
                if not isinstance(obj, type):
                    warnings.warn(f'could not restore instance data for {obj}')
        return obj

    def isdipped(self, data_or_obj):
        obj = tryOr(lambda: dill.loads(data_or_obj), None) if not isinstance(data_or_obj, dict) else data_or_obj
        return isinstance(obj, dict) and obj.get('__dipped__') == self.__calories


dilldip = _DillDip()
