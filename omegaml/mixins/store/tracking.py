class TrackableMetadataMixin:
    """ plugin for models store to allow linking experiments
    """

    @classmethod
    def supports(cls, store, **kwargs):
        return store.prefix in ('models/')

    def link_experiment(self, name, experiment, label=None):
        """
        This links a model to an experiment by adding the experiment name to the
        list of metadata.tracking.experiments. Note this is different from the
        runtime's .track() method, which sets the default experiment for a model
        to be tracked by.

        Args:
            name (str): the name of the model
            experiment (str): the name of the experiment
            label (str): the runtime label to use. If not set, the experiment
                will not be tracked by the runtime. Use the runtime's .track()
                method to track the experiment by the runtime.

        Returns:
            Metadata()
        """
        meta = self.metadata(name)
        tracking = meta.attributes.setdefault('tracking', {})
        exps = tracking.setdefault('experiments', [])
        if experiment not in exps:
            meta.attributes['tracking']['experiments'].append(experiment)
        if label:
            meta.attributes.setdefault('tracking', {})
            meta.attributes['tracking'].update({
                label: experiment
            })
        return meta.save()


class UntrackableMetadataMixin:
    """ placeholder for objects other than models (future use)
    """

    # this enables simplified code in OmegaTask.enable_delegate_tracking
    @classmethod
    def supports(cls, store, **kwargs):
        return not store.prefix in ('models/')

    def link_experiment(self, name, experiment, label=None):
        return self.metadata(name)
