from .modelmixin import ModelMixin
from .gridsearch import GridSearchMixin
from ...util import extend_instance


class RuntimeProxy:
    def _apply_mixins(self):
        """
        apply mixins in defaults.OMEGA_RUNTIME_MIXINS
        """
        from omegaml import settings
        defaults = settings()
        for mixin in defaults.OMEGA_RUNTIME_MIXINS:
            conditional = self._mixins_conditional
            extend_instance(self, mixin,
                            conditional=conditional)

    def _mixins_conditional(self, cls, obj):
        return cls.supports(obj) if hasattr(cls, 'supports') else True
