from __future__ import absolute_import

import logging

from omegaml.util import extend_instance

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
        self._apply_mixins()

    def run(self, timeout=None, **kwargs):
        """
        submit the job for immediate execution

        Args:
            timeout (int): optional, timeout in seconds
            **kwargs: kwargs to CeleryTask.delay

        Returns:
            AsyncResult
        """
        job_run = self.runtime.task('omegaml.notebook.tasks.run_omegaml_job')
        return job_run.delay(self.jobname, timeout=timeout, **kwargs)

    def schedule(self, **kwargs):
        """
        schedule the job for repeated execution

        Args:
            **kwargs: see OmegaJob.schedule()
        """
        job_run = self.runtime.task('omegaml.notebook.tasks.schedule_omegaml_job')
        return job_run.delay(self.jobname, **kwargs)

    def _apply_mixins(self):
        """
        apply mixins in defaults.OMEGA_STORE_MIXINS
        """
        for mixin in self.runtime.omega.defaults.OMEGA_JOBPROXY_MIXINS:
            extend_instance(self, mixin)
