import warnings


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
            tracking['experiments'].append(experiment)
        if label:
            tracking.update({
                label: experiment
            })
        return meta.save()

    def link_monitor(self, name, experiment, provider=None, event='drift',
                     alerts=None, schedule=None):
        """
        This links a model to a monitor by adding the experiment name to the
        list of metadata.tracking.monitors.

        Args:
            name (str): the name of the model
            experiment (str): the name of the experiment
            event (str): the event to monitor, defaults to 'drift'
            alerts (list): a list of alert definitions. Each alert definition
              is a dict with keys 'event', 'recipients'. 'event' is the event
              to get from the tracking log, 'recipients' is a list of recipients
              (e.g. email address, notification channel)
            schedule (str): the job scheduling interval for the monitoring job,
               as used in om.jobs.schedule() when the job is created

        Returns:
            Metadata()
        """
        meta = self.metadata(name)
        tracking = meta.attributes.setdefault('tracking', {})
        monitors = tracking.setdefault('monitors', [])
        # update existing monitor, if any
        for mon in monitors:
            if mon['experiment'] == experiment:
                mon.update({
                    'provider': provider or mon.get('provider'),
                    'alerts': alerts or mon.get('alerts'),
                    'schedule': schedule or mon.get('schedule')
                })
                break
        else:
            specs = {
                'experiment': experiment,
                'provider': provider or 'default',
                'alerts': alerts or [{
                    'event': event,
                    'recipients': [],
                }],
                'schedule': schedule or 'daily',
            }
            monitors.append(specs)
        return meta.save()


class UntrackableMetadataMixin:
    """ placeholder for objects other than models (future use)
    """

    # this enables simplified code in OmegaTask.enable_delegate_tracking
    @classmethod
    def supports(cls, store, **kwargs):
        return not store.prefix in ('models/')

    def link_experiment(self, name, experiment, **kwargs):
        warnings.warn('link_experiment is not supported for {self.prefix} store')
        return self.metadata(name)

    def link_monitor(self, name, experiment, **kwargs):
        warnings.warn('link_monitor is not supported for {self.prefix} store')
        return self.metadata(name)
