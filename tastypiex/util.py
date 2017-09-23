from importlib import import_module
import sys

def load_api(qualif):
    """
    load Api instances from a string spec module.attr
    
    # module path.to.module.api.py
    api_v1 = Api(...)
    ...
    # somewhere
    load_api('path.to.module.api.api_v1')
    """
    parts = qualif.split('.')
    modname, apiattr = '.'.join(parts[0:-1]), parts[-1]
    try:
        if modname in sys.modules:
            mod = sys.modules.get(modname)
        else:
            mod = import_module(modname)
        api = getattr(mod, apiattr)
    except AttributeError as e:
        raise AttributeError('Cannot load api from %s, due to %s' % 
                             (modname, e))
    return api
    