from __future__ import absolute_import

import logging
from uuid import uuid4

import six

from omegaml.runtimes import OmegaJobProxy
from omegaml.util import is_dataframe, settings, is_ndarray

logger = logging.getLogger(__file__)


class OmegaAuthenticatedJobProxy(OmegaJobProxy):
    """
    proxy to a remote job in a celery worker

    Usage:

        .. code::

            om = Omega()
            # result is AsyncResult, use .get() to return it's result
            result = om.runtime.job('foojob').run()
            result.get()

            # result is AsyncResult, use .get() to return it's result
            result = om.runtime.job('foojob').schedule()
            result.get()
    """

    @property
    def _common_kwargs(self):
        return dict(__auth=self.runtime.auth_tuple)
