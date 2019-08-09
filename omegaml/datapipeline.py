from sklearn.utils import Parallel, delayed


class ParallelStep(object):
    def __init__(self, steps=None, agg=None, n_jobs=-1):
        self.steps = steps
        self.agg = agg or np.mean
        self.n_jobs = n_jobs

    def aggregate(self, values):
        return self.agg(values)

    def __call__(self, value):
        values = Parallel(n_jobs=self.n_jobs)(delayed(pfn)(value) for pfn in self.steps)
        return self.aggregate(values)


class DataPipeline(object):
    def __init__(self, steps):
        self.steps = steps
        self.args = None
        self.kwargs = None

    def set_params(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        return self

    def process(self, value=None):
        for stepfn in self.steps:
            value = stepfn(value)
        return value

    def __call__(self):
        return self.process()


