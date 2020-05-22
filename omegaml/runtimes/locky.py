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
        super().__init__(*args, **kwargs)

    def start_call(self):
        self.tqdm = tqdm(total=self._job_count, unit='tasks')
        self._orig_print_progress = self.parallel.print_progress
        self.parallel.print_progress = self.update_progress

    def update_progress(self):
        try:
            self.tqdm.update(1)
        except:
            self._origin_print_progress()

    def stop_call(self):
        try:
            self.tqdm.close()
        except:
            self._origin_print_progress()

    def terminate(self):
        try:
            self.tqdm.close()
        finally:
            super().terminate()

#: register joblib parallel omegaml  backend
joblib.register_parallel_backend('omegaml', OmegaRuntimeBackend)
