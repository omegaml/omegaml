from __future__ import absolute_import

import logging

from omegaml.runtimes.proxies.baseproxy import RuntimeProxyBase

logger = logging.getLogger(__name__)


class OmegaModelProxy(RuntimeProxyBase):
    """
    proxy to a remote model in a celery worker

    The proxy provides the same methods as the model but will
    execute the methods using celery tasks and return celery
    AsyncResult objects

    Usage::

        om = Omega()
        # train a model
        # result is AsyncResult, use .get() to return it's result
        result = om.runtime.model('foo').fit('datax', 'datay')
        result.get()

        # predict
        result = om.runtime.model('foo').predict('datax')
        # result is AsyncResult, use .get() to return it's result
        print result.get()

    Notes:
        The actual methods of ModelProxy are defined in its mixins

    See Also:
        * ModelMixin
        * GridSearchMixin
    """
    #     Implementation note:
    #
    #     We decided to implement each method call explicitely in both
    #     this class (mixins) and the celery tasks. While it would be possible to
    #     implement a generic method and task that passes the method and
    #     arguments to be called, maintainability would suffer and the
    #     documentation would become very unspecific. We think it is much
    #     cleaner to have an explicit interface at the chance of missing
    #     features. If need should arise we can still implement a generic
    #     method call.

    def __init__(self, modelname, runtime=None):
        super().__init__(modelname, runtime=runtime, store=runtime.omega.models)
        self.modelname = modelname

    def task(self, name):
        """
        return the task from the runtime with requirements applied
        """
        return self.runtime.task(name)

    def experiment(self, experiment=None, label=None, provider=None):
        """ return the experiment for this model

        If an experiment does not exist yet, it will be created. The
        experiment is automatically set to track this model, unless another
        model has already been set to track this model for the same label.
        If a previous model has been set to track this model it will be
        returned. If an experiment name is passed it will be used.

        Args:
            experiment (str): the experiment name, defaults to the modelname
            label (str): the runtime label, defaults to 'default'
            provider (str): the provider to use, defaults to 'default'

        Returns:
            OmegaTrackingProxy() instance
        """
        label = label or self.runtime._default_label
        exps = self.experiments(label=label) if experiment is None else None
        exp = exps[0] if exps else None
        experiment = experiment or self.modelname
        if exp is None:
            exp = self.runtime.experiment(experiment, provider=provider)
            if not label in self.experiments():
                exp.track(self.modelname, label=label)
        return exp

    def experiments(self, label=None, raw=False):
        """ return list of experiments tracking this model

        Args:
            label (None|str): if set, return only the experiment for this label
            raw (bool): if True return the metadata for the experiment, else return the OmegaTrackingProxy

        Returns:
            list of OmegaTrackingProxy instances or Metadata objects
        """
        store = self.store
        tracking = (store.metadata(self.modelname).attributes.get('tracking', {}))
        names = [tracking.get(label)] if label in tracking else None
        names = names or (tracking.get('experiments', []) if not (label or names) else [])
        return [self.runtime.experiment(name) if not raw else store.metadata(f'experiments/{name}')
                for name in names]
