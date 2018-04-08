from __future__ import absolute_import

import logging
from uuid import uuid4

import six

from omegaml.util import is_dataframe, settings, is_ndarray

logger = logging.getLogger(__file__)


class OmegaScriptProxy(object):
    """
    proxy to a remote job in a celery worker

    Usage:

        .. code::

            om = Omega()
            # result is AsyncResult, use .get() to return it's result
            result = om.runtime.script('foojob').run()
            result.get()
    """

    def __init__(self, scriptname, runtime=None):
        self.scriptname = scriptname
        self.runtime = runtime

    def run(self, **kwargs):
        """
        run the script

        Runs the script and returns its result as

        {"runtime": 7.4e-05,
          "started": "2018-04-07T17:57:52.451012",
          "kwargs": {},
          "result": {},
          "script": "helloworld"
        }

        :return: the result
        """
        script_run = self.runtime.task('omegapkg.tasks.run_omega_script')
        return script_run.delay(self.scriptname, auth=self.runtime.auth_tuple,
                                **kwargs)
