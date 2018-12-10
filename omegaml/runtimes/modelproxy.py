from __future__ import absolute_import

import logging
from uuid import uuid4

import six

from omegaml.util import is_dataframe, settings, is_ndarray, extend_instance
logger = logging.getLogger(__file__)


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
        self.pure_python = getattr(settings(), 'OMEGA_FORCE_PYTHON_CLIENT',
                                   False)
        self.pure_python = self.pure_python or self._client_is_pure_python()
        self.apply_mixins()

    def apply_mixins(self):
        """
        apply mixins in defaults.OMEGA_RUNTIME_MIXINS
        """
        from omegaml import defaults
        for mixin in defaults.OMEGA_RUNTIME_MIXINS:
            extend_instance(self, mixin)

    def _client_is_pure_python(self):
        try:
            import pandas as pd
            import numpy as np
            import sklearn
        except Exception as e:
            logging.getLogger().info(e)
            return True
        else:
            return False
