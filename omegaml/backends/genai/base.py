from types import FunctionType

from omegaml.backends.virtualobj import VirtualObjectBackend, VirtualObjectHandler


class GenAIBaseBackend(VirtualObjectBackend):
    KIND = 'genai.llm'

    @classmethod
    def supports(self, obj, name, **kwargs):
        return isinstance(obj, GenAIModel) or hasattr(obj, '_omega_virtual_genai')

    def _ensure_handler_instance(self, obj):
        # always return a handler instance
        obj = super()._ensure_handler_instance(obj)
        if hasattr(obj, '_omega_virtual_genai') and isinstance(obj, FunctionType):
            obj = GenAIModel(fn=obj)
        return obj

    def _resolve_input_data(self, method, Xname, **kwargs):
        # TODO this should not be necessary, the data should be resolved by super()
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
        model : GenAIModel
        model = self.get(modelname)
        model.load('complete')
        data = self._resolve_input_data('complete', Xname, **kwargs)
        data = data[0] if isinstance(data, list) else data
        if isinstance(data, dict):
            prompt = data.get('prompt', '')
            messages = data.get('messages')
            conversation_id = data.get('conversation_id')
        elif isinstance(data, str):
            prompt = data or ''
            messages = None
            conversation_id = None
        else:
            raise ValueError(f'Invalid input data, expected dict or str, got {type(data)}')
        return model.complete(prompt, messages=messages, conversation_id=conversation_id, **kwargs)

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


class GenAIModel(VirtualObjectHandler):
    _omega_virtual = False
    _omega_virtual_genai = True

    def __init__(self, *args, fn=None, **kwargs):
        if callable(fn):
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

    def load(self, method):
        pass

    def complete(self, prompt, conversation_id=None, **kwargs):
        raise NotImplementedError

    def generate(self, *args, **kwargs):
        raise NotImplementedError

    def finetune(self, *args, **kwargs):
        raise NotImplementedError

    def embed(self, *args, **kwargs):
        raise NotImplementedError


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
