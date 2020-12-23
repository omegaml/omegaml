from contextlib import contextmanager

from celery import chain, group, chord


class CanvasTask:
    """
    support for canvas tasks

    See Also
        om.runtime.sequence
        om.runtime.parallel
        om.runtime.mapreduce
    """

    def __init__(self, canvasfn):
        self.sigs = []
        self.canvasfn = canvasfn
        self.runtime = None

    def add(self, task):
        self.sigs.append(task)

    def delay(self, *args, **kwargs):
        return self.apply_async(args=args, kwargs=kwargs)

    def apply_async(self, args=None, kwargs=None, **celery_kwargs):
        task = self.sigs[-1]
        task._apply_kwargs(kwargs, celery_kwargs)
        if self.canvasfn is chord:
            sig = task.task.signature(args=args, kwargs=kwargs, **celery_kwargs, immutable=False)
        else:
            # immutable means results are not passed on from task to task
            sig = task.task.signature(args=args, kwargs=kwargs, **celery_kwargs, immutable=True)
        self.sigs[-1] = sig
        return sig

    def run(self):
        if self.canvasfn is chord:
            result = self.canvasfn(self.sigs[:-1])(self.sigs[-1])
        else:
            result = self.canvasfn(*self.sigs).apply_async()
        return result


def make_canvased(canvasfn):
    @contextmanager
    def canvased(self):
        """
        context manager to support sequenced, parallel and mapreduce tasks

        Usage:
            # run tasks async, in sequence
            with om.runtime.sequence() as crt:
                crt.model('mymodel').fit(...)
                crt.model('mymodel').predict(...)
                result = crt.run()

            # run tasks async, in parallel
            with om.runtime.parallel() as crt:
                crt.model('mymodel').predict(...)
                crt.model('mymodel').predict(...)
                result = crt.run()

            # run tasks async, in parallel with a final step
            with om.runtime.mapreduce() as crt:
                # map tasks
                crt.model('mymodel').predict(...)
                crt.model('mymodel').predict(...)
                # reduce results - combined is a virtualobj function
                crt.model('combined').reduce(...)
                result = crt.run()

            # combined is a virtual obj function, e.g.
            @virtualobj
            def combined(data=None, **kwargs):
                # data is the list of results from each map step
                return data

            Note that the statements inside the context are
            executed in sequence, as any normal python code. However,
            the actual tasks are only executed on calling crt.run()

        Args:
            self: the runtime

        Returns:
            None
        """
        canvas = CanvasTask(canvasfn)
        _orig_task = self.task

        def canvas_task(*args, **kwargs):
            task = _orig_task(*args, **kwargs)
            canvas.add(task)
            return canvas

        self.task = canvas_task
        canvas.runtime = self
        canvas.runtime.run = canvas.run
        try:
            yield canvas.runtime
        finally:
            canvas.runtime.task = _orig_task
            canvas.runtime.run = None

    return canvased


canvas_chain = make_canvased(chain)
canvas_group = make_canvased(group)
canvas_chord = make_canvased(chord)
