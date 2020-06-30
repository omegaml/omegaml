from __future__ import absolute_import

import logging

from omegaml.util import extend_instance

logger = logging.getLogger(__name__)


class OmegaModelProxy(object):
    """
    proxy to a remote model in a celery worker

    The proxy provides the same methods as the model but will
    execute the methods using celery tasks and return celery
    AsyncResult objects

    Usage:

        .. code::

            om = Omega()
            # train a model
            # result is AsyncResult, use .get() to return it's result
            result = om.runtime.model('foo').fit('datax', 'datay')
            result.get()

            # predict
            result = om.runtime.model('foo').predict('datax')
            # result is AsyncResult, use .get() to return it's result
            print result.get()
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
        self.modelname = modelname
        self.runtime = runtime
        self.apply_mixins()
        self.apply_require()

    def apply_require(self):
        meta = self.runtime.omega.models.metadata(self.modelname)
        assert meta is not None, "model {self.modelname} does not exist".format(**locals())
        require_kwargs = meta.attributes.get('require')
        self.runtime.require(**require_kwargs) if require_kwargs else None

    def apply_mixins(self):
        """
        apply mixins in defaults.OMEGA_RUNTIME_MIXINS
        """
        from omegaml import settings
        defaults = settings()
        for mixin in defaults.OMEGA_RUNTIME_MIXINS:
            extend_instance(self, mixin)

    def task(self, name):
        """
        return the task from the runtime with requirements applied
        """
        return self.runtime.task(name)
