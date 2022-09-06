from omegaml.runtimes import OmegaModelProxy


class ScaffoldMixin:
    @classmethod
    def supports(cls, obj):
        return isinstance(obj, (OmegaModelProxy))

    def api(self, resource_name):
        pass


class ApiScaffold:
    def __init__(self, resource_name):
        pass

    def curl(self):
        pass

    def requests(self):
        pass

    def call(self):
        pass


