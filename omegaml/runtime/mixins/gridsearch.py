class GridSearchMixin(object):
    def gridsearch(self, Xname, Yname, parameters=None, pure_python=False, **kwargs):
        gs_task = self.runtime.task('omegaml.tasks.omega_gridsearch')
        Xname = self._ensure_data_is_stored(Xname, prefix='_fitX')
        if Yname is not None:
            Yname = self._ensure_data_is_stored(Yname, prefix='_fitY')
        return gs_task.delay(self.modelname, Xname, Yname, parameters=parameters,
                             auth=self.runtime.auth_tuple,
                             pure_python=self.pure_python, **kwargs)
