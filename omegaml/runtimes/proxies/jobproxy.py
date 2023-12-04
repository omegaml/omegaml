from __future__ import absolute_import

import logging

from omegaml.runtimes.proxies.baseproxy import RuntimeProxyBase

logger = logging.getLogger(__file__)


class OmegaJobProxy(RuntimeProxyBase):
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
        super().__init__(jobname, runtime=runtime, store=runtime.omega.jobs)
        self.jobname = jobname

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

    @property
    def _mixins(self):
        return self.runtime.omega.defaults.OMEGA_JOBPROXY_MIXINS
