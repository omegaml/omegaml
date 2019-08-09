from __future__ import absolute_import

import datetime
from importlib import import_module
import os

from omegaml.runtimes.jobproxy import OmegaJobProxy


class DaskTask(object):
    """
    A dask remote function wrapper mimicking a Celery task
    """

    def __init__(self, fn, client, pure=True, **kwargs):
        """
        :param fn: (function) the function to be called
        :param client: (dask client) the dask client to use
        :param pure: (bool) whether this is a dask pure function (will
            be cached or not). Defaults to True.
        """
        self.client = client
        self.fn = fn
        self.pure = pure
        self.kwargs = kwargs

    def delay(self, *args, **kwargs):
        """
        submit the function and execute on cluster.  
        """
        kwargs['pure'] = kwargs.get('pure', self.pure)
        if self.kwargs:
            kwargs.update(self.kwargs)
        return DaskAsyncResult(self.client.submit(self.fn, *args, **kwargs))


class DaskAsyncResult(object):
    """
    A dask Future wrapper mimicking a Celery AsyncResult
    """

    def __init__(self, future):
        self.future = future

    def get(self):
        import dask

        if os.environ.get('DASK_DEBUG'):
            with dask.set_options(get=dask.threaded.get):
                return self.future.result()
        return self.future.result()


def daskhello(*args, **kwargs):
    # test function for dask distributed
    return "hello from {} at {}".format(os.getpid(), datetime.datetime.now())


class OmegaRuntimeDask(object):
    """
    omegaml compute cluster gateway to a dask distributed cluster

    set environ DASK_DEBUG=1 to run dask tasks locally
    """

    def __init__(self, omega, dask_url=None):
        self.dask_url = dask_url
        self.omega = omega
        self._client = None

    @property
    def client(self):
        from distributed import Client, LocalCluster
        if self._client is None:
            if os.environ.get('DASK_DEBUG'):
                # http://dask.pydata.org/en/latest/setup/single-distributed.html?highlight=single-threaded#localcluster
                single_threaded = LocalCluster(processes=False)
                self._client = Client(single_threaded)
            else:
                self._client = Client(self.dask_url)
        return self._client

    def model(self, modelname):
        """
        return a model for remote execution
        """
        from omegaml.runtimes.modelproxy import OmegaModelProxy
        return OmegaModelProxy(modelname, runtime=self)

    def job(self, jobname):
        """
        return a job for remote exeuction
        """
        return OmegaJobProxy(jobname, runtime=self)

    def task(self, name, **kwargs):
        """
        retrieve the task function from the task module

        This retrieves the task function and wraps it into a 
        DaskTask. DaskTask mimicks a celery task and is 
        called on the cluster using .delay(), the same way we
        call a celery task. .delay() will return a DaskAsyncResult,
        supporting the celery .get() semantics. This way we can use
        the same proxy objects, as all they do is call .delay() and
        return an AsyncResult. 
        """
        modname, funcname = name.rsplit('.', 1)
        mod = import_module(modname)
        func = getattr(mod, funcname)
        # we pass pure=False to force dask to reevaluate the task
        # http://distributed.readthedocs.io/en/latest/client.html?highlight=pure#pure-functions-by-default
        return DaskTask(func, self.client, pure=False, **kwargs)

    def settings(self):
        """
        return the runtimes's cluster settings
        """
        return self.task('omegaml.tasks.omega_settings').delay().get()

    def ping(self):
        return DaskTask(daskhello, self.client, pure=False)
