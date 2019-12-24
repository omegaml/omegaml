from __future__ import absolute_import

import logging
from uuid import uuid4

import six

from omegaml.util import is_dataframe, settings, is_ndarray
logger = logging.getLogger(__file__)


class OmegaJobProxy(object):

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
    def __init__(self, jobname, runtime=None):
        self.jobname = jobname
        self.runtime = runtime

    def run(self, **kwargs):
        """
        run the job

        :return: the result
        """
        job_run = self.runtime.task('omegaml.notebook.tasks.run_omegaml_job')
        return job_run.delay(self.jobname, **kwargs)

    def schedule(self, **kwargs):
        """
        schedule the job
        """
        job_run = self.runtime.task('omegaml.notebook.tasks.schedule_omegaml_job')
        return job_run.delay(self.jobname, **kwargs)
