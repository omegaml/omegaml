from tqdm import tqdm
import joblib

LokyBackend = joblib.parallel.BACKENDS['loky']


class OmegaRuntimeBackend(LokyBackend):
    """
    omega custom parallel backend to print progress

    TODO: extend for celery dispatching
    """
    def __init__(self, *args, **kwargs):
        self._tqdm = None
        self._job_count = kwargs.pop('n_tasks', None)
        self._verbose = kwargs.pop('verbose', True)
        import multiprocessing as mp
        # get LokyBackend to run in Celery, see LokyBackend.effective_n_jobs
        # TODO replace mp with billiard
        mp.current_process().daemon = False
        super().__init__(*args, **kwargs)

    def start_call(self):
        if self._verbose:
            self.tqdm = tqdm(total=self._job_count, unit='tasks')
        self._orig_print_progress = self.parallel.print_progress
        self.parallel.print_progress = self.update_progress

    def update_progress(self):
        try:
            self.tqdm.update(1) if self._verbose else None
        except:
            pass

    def stop_call(self):
        try:
            self.tqdm.close()
        except:
            pass

    def terminate(self):
        try:
            self.tqdm.close()
        except:
            pass
        finally:
            super().terminate()

#: register joblib parallel omegaml  backend
joblib.register_parallel_backend('omegaml', OmegaRuntimeBackend)
