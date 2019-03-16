from omegaml.runtimes.mixins import ModelMixin


class AuthenticatedModelMixin(ModelMixin):
    @property
    def _common_kwargs(self):
        return dict(__auth=self.runtime.auth_tuple, pure_python=self.pure_python)


