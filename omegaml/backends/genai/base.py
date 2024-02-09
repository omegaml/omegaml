from types import FunctionType

from omegaml.backends.virtualobj import VirtualObjectBackend, VirtualObjectHandler


class GenAIBaseBackend(VirtualObjectBackend):
    """ Generic backend to store user-implemented AI model handlers

    This handles storage and retrieval for GenAIModelHandler subclasses
    and instances, and provides bindings for the runtime to call using
    e.g. backend.perform('complete', 'mymodel', 'X'). Works the same
    as VirtualObjectBackend, but with a different KIND and supports
    other methods.
    """
    KIND = 'genai.llm'

    @classmethod
    def supports(self, obj, name, **kwargs):
        return isinstance(obj, GenAIModel) or hasattr(obj, '_omega_virtual_genai')

    def _ensure_handler_instance(self, obj):
        # always return a handler instance
        obj = super()._ensure_handler_instance(obj)
        if hasattr(obj, '_omega_virtual_genai') and isinstance(obj, FunctionType):
            obj = GenAIModelHandler(fn=obj)
        return obj

    def _resolve_input_data(self, method, Xname, **kwargs):
        # TODO this should not be necessary, the data should be resolved by super()
        #      it is not because VirtualObjectBackend is not a ModelBackend
        data = self.data_store.get(Xname)
        meta = self.data_store.metadata(Xname)
        if self.tracking:
            self.tracking.log_event(method, 'X', {
                'Xname': Xname,
                'data': data,
                'kind': meta.kind,
            })
        return data

    def complete(self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        # Xname is the input given by the user
        model: GenAIModel
        model = self.get(modelname)
        model.load('complete')
        data = self._resolve_input_data('complete', Xname, **kwargs)
        data = data[0] if isinstance(data, list) else data
        if isinstance(data, dict):
            # a qualified prompt, possibly as a chat
            prompt = data.get('prompt', '')
            messages = data.get('messages')
            user_data = data.get('data')
            chat = data.get('chat', False)
            conversation_id = data.get('conversation_id')
        elif isinstance(data, str):
            # just a single prompt, assume no chat
            prompt = data or ''
            chat = False
            messages = None
            conversation_id = None
            user_data = None
        else:
            raise ValueError(f'Invalid input data, expected dict or str, got {type(data)}')
        return model.complete(prompt, messages=messages, conversation_id=conversation_id,
                              data=user_data, chat=chat, **kwargs)

    def generate(self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        model = self.get(modelname)
        model.load('generate')
        data = self._resolve_input_data('generate', Xname, **kwargs)
        return model.generate(data)

    def embed(self, modelname, Xname, rName=None, pure_python=True, **kwargs):
        model = self.get(modelname)
        model.load('embed')
        data = self._resolve_input_data('embed', Xname, **kwargs)
        return model.embed(data)

    def predict(self, *args, **kwargs):
        raise NotImplementedError('A GenAIModel does not support prediction, use complete or generate')


class GenAIModel:
    # model interface for GenAIModelHandler, should not be used directly
    def load(self, method):
        pass

    def complete(self, prompt, messages=None, conversation_id=None,
                 data=None, **kwargs):
        raise NotImplementedError

    def generate(self, *args, **kwargs):
        raise NotImplementedError

    def finetune(self, *args, **kwargs):
        raise NotImplementedError

    def embed(self, *args, **kwargs):
        raise NotImplementedError


class GenAIModelHandler(GenAIModel, VirtualObjectHandler):
    """
    A base class to implement user-provided AI model handlers

    Usage:
        class MyModelHandler(GenAIModelHandler):
            def load(self, method):
                # code to load the model or pipeline for a given method
                # method is one of 'complete', 'generate', 'finetune', 'embed'
                self.model = ...

            def complete(self, ):
                # code to run model's completion
                return X

            ...

        # publish model
        om.models.put(MyModelHandler, 'mygenai')

        # get model
        model = om.models.get('mygenai')
        model.complete()

        # use via runtime
        om.runtime.model('mygenai').complete(prompt='hello, how are you'?)

    Notes:
        * as with other VirtualObjectHandlers, the implementation of each
          method must be self-contained and not rely on global objects or
          imports
        * if you need global imports, use .load() to import them
          and store them as instance attributes (e.g. import torch, self.torch = torch)
        * all methods called are guaranteed to call .load() before calling the
          actual method, subsequent calls will re-instantiate the handler and thus
          call .load() again (i.e. do not assume caching across calls)
    """
    _omega_virtual = False
    _omega_virtual_genai = True

    def __init__(self, *args, fn=None, **kwargs):
        if callable(fn):
            # map this instance's GenAIModel methods to the fn
            model_methods = ['load', 'complete', 'generate', 'finetune', 'embed']
            fn_caller = lambda m: lambda *a, **kw: fn(*a, method=m, **kw)
            for method in model_methods:
                setattr(self, method, fn_caller(method))

        super().__init__(*args, **kwargs)

    def _vobj_call_map(self):
        return {
            'complete': self.complete,
            'generate': self.generate,
            'finetune': self.finetune,
        } | super()._vobj_call_map()

    @classmethod
    def wrap(cls, fn):
        return GenAIModel(fn=fn)


def virtual_genai(fn):
    """
    function decorator to create a virtual genai model handler from any
    callable

    Args:
        fn: the virtual handler function

    Usage:

        .. code::

            @virtual_genai
            def myvirtualobj(data=None, method=None, meta=None, store=None, **kwargs):
                ...
    See:
        VirtualObjectBackend for details on virtual object handlers

    Returns:
        fn
    """
    setattr(fn, '_omega_virtual_genai', True)
    return fn
