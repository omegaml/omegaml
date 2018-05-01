import os
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
            test_mode = any('test' in v for v in sys.argv)
            cached = self.data.get(func)
            if cached is not None:
                age = datetime.now() - cached['fetch_time']
                refetch = (age > self.max_age)
            if test_mode or cached is None or refetch:
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
    from omegaml import load_class
    cls = load_class(cls)
    if cls not in obj.__class__.mro():
        base_cls = obj.__class__
        base_cls_name = 'Extended{}'.format(obj.__class__.__name__.split('.')[0])
        obj.__class__ = type(base_cls_name, (cls, base_cls), {})

def mkdirs(path):
    """ save os.makedirs for python 2 & 3
    """
    if not os.path.exists(path):
        os.makedirs(path)