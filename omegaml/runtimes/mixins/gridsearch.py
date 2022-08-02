class GridSearchMixin(object):
    def gridsearch(self, Xname, Yname=None, parameters=None, pure_python=False, **kwargs):
        """ run gridsearch on model

        Args:
            Xname (str|obj): the name of the X dataset in om.datasets, or
                the data object
            Yname (str|obj): the name of the Y dataset in om.datasets, or
                the data object
            parameters (dict): input to GridSearchCV(..., param_grid=parameters)

        See Also:
            * sklearn.model_selection.GridSearchCV
        """
        gs_task = self.task('omegaml.tasks.omega_gridsearch')
        Xname = self._ensure_data_is_stored(Xname, prefix='_fitX')
        if Yname is not None:
            Yname = self._ensure_data_is_stored(Yname, prefix='_fitY')
        return gs_task.delay(self.modelname, Xname, Yname=Yname, parameters=parameters, **kwargs)
