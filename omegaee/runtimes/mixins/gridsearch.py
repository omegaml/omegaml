from omegaml.runtimes.mixins import GridSearchMixin


class AuthenticatedGridSearchMixin(GridSearchMixin):
    @property
    def _common_kwargs(self):
        return dict(__auth=self.runtime.auth_tuple, pure_python=self.pure_python)


