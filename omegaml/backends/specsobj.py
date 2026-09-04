from omegaml.backends.virtualobj import VirtualObjectBackend
from omegaml.client.util import subdict, subdict_except


class SpecsMixin:
    """This mixin and the corresponding SpecsBacked allows a class to be saved (pickled) and reloaded
    based on a specification.

    How this works:
        The specs=['var', ...] kwarg provided on class instantiation provides a list of instance variables
        that will be used to represent the specification and state of an object instance, whereas the
        actual implementation of the specification is created by the .load() method. This allows for lazy
        loading.
    """

    def __init__(self, specs: object = None, load: object = False, **kwargs: object) -> None:
        kwargs = {**(specs if isinstance(specs, dict) else {}), **kwargs}
        specs = list(specs.keys()) if isinstance(specs, dict) else specs
        self._specs = specs or list(kwargs.keys())
        self.initialize(load=load, **kwargs)

    def initialize(self, load=False, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)  # spec value
            setattr(self, f'_{k}', None)  # implementation
        self.load() if load else None

    def load(self):
        pass

    @property
    def specs(self):
        return {k: getattr(self, k) for k in self._specs}

    def __getstate__(self):
        return self.specs

    def __setstate__(self, state):
        self._specs = list(state.keys())
        self.initialize(**state, load=False)


class SpecsBackend(VirtualObjectBackend):
    KIND = 'python.specs'

    @classmethod
    def supports(cls, obj, name, **kwargs):
        return isinstance(obj, SpecsMixin)

    def put(self, obj, name, **kwargs):
        attributes = kwargs.get('attributes') or {}
        attributes.update(obj.specs)
        kwargs['attributes'] = attributes
        meta = super().put(obj, name, **kwargs)
        return meta.save()

    def get(self, name, load=True, tracking=None, **kwargs):
        meta = self.model_store.metadata(name)
        obj = super().get(name, **kwargs)
        obj.initialize(
            load=load,
            tracking=tracking or self.tracking,
            **{**subdict_except(subdict(meta.attributes, obj.specs.keys()), ['tracking']), **kwargs},
        )
        return obj
