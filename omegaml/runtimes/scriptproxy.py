from __future__ import absolute_import

import logging

logger = logging.getLogger(__file__)


class OmegaScriptProxy(object):
    """
    proxy to a remote job in a celery worker

    Usage:

        .. code::

            om = Omega()
            # result is AsyncResult, use .get() to return it's result
            result = om.runtimes.script('foojob').run()
            result.get()
    """

    def __init__(self, scriptname, runtime=None):
        self.scriptname = scriptname
        self.runtime = runtime

    def run(self, as_callback=False, **kwargs):
        """
        run the script

        Runs the script and returns its result as

        {"runtimes": 7.4e-05,
          "started": "2018-04-07T17:57:52.451012",
          "kwargs": {},
          "result": {},
          "script": "helloworld"
        }

        :return: the result
        """
        script_run = self.task(as_callback=as_callback)
        return script_run.delay(self.scriptname, **kwargs)

    def task(self, as_callback=False):
        task_name = 'run_omega_callback_script' if as_callback else 'run_omega_script'
        return self.runtime.task(f'omegaml.backends.package.tasks.{task_name}')
