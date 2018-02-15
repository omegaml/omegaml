from datetime import datetime, timedelta
import sys


class cached(object):
    # adopted from https://stackoverflow.com/a/30698822

    def __init__(self, seconds=-1):
        self.data = {}
        self.max_age = timedelta(
            seconds=seconds) if seconds > 0 else sys.maxint

    def __call__(self, func):
        def inner(*args, **kwargs):
            cached = self.data.get(func)
            if cached is not None:
                age = datetime.now() - cached['fetch_time']
                refetch = (age > self.max_age)
            if (cached is None or refetch):
                resp = func(*args, **kwargs)
                self.data[func] = {
                    'data': resp,
                    'fetch_time': datetime.now()
                }
                cached = self.data[func]
            return cached['data']
        return inner


def extend_instance(obj, cls):
    """Apply mixins to a class instance after creation"""
    # source https://stackoverflow.com/a/31075641
    base_cls = obj.__class__
    base_cls_name = obj.__class__.__name__
    obj.__class__ = type(base_cls_name, (cls, base_cls),{})