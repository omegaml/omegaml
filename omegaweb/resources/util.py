class BundleObj(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


isTrue = lambda v: v if isinstance(v, bool) else (
    v.lower() in ['yes', 'y', 't', 'true', '1'])
