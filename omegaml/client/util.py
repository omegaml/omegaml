def protected(kw):
    return '__' + kw


def get_omega(args, require_config=False):
    from omegaml import setup, _base_config
    from omegaml.client.cloud import setup_from_config
    config_file = args.get('--config')
    # deprecated, use --local
    local_runtime = args.get('--local-runtime')
    local = args.get('--local')
    if local or local_runtime:
        _base_config.OMEGA_LOCAL_RUNTIME = True
    bucket = args.get('--bucket')
    if config_file or require_config:
        try:
            om = setup_from_config(config_file)
        except Exception as e:
            msg = (f'Config file could not be found due to {e}. Specify as --config or set '
                   'OMEGA_CONFIG_FILE env variable')
            raise ValueError(msg)
    else:
        om = setup()
    if local or local_runtime:
        om.runtime.mode(local=True)
    return om[bucket] if bucket else om  # for speed


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class dotable(dict):
    """" dot-accessible, recursive dictionary, e.g. d['key'] -> d.key """
    # adopted from: https://stackoverflow.com/a/3031270/890242
    MARKER = object()

    def __init__(self, value=None):
        super().__init__()
        if value is None:
            pass
        elif isinstance(value, dict):
            for key in value:
                self.__setitem__(key, value[key])
        else:
            raise TypeError('expected dict')

    def __setitem__(self, key, value):
        if isinstance(value, dict) and not isinstance(value, dotable):
            value = dotable(value)
        elif isinstance(value, (list, tuple)):
            value = [dotable(x) if isinstance(x, dict) and not isinstance(x, dotable) else x for x in value]
        super(dotable, self).__setitem__(key, value)

    def __getitem__(self, key):
        found = self.get(key, dotable.MARKER)
        if found is dotable.MARKER:
            raise KeyError(key)
        return found

    def __getattr__(self, key):
        found = self.get(key, dotable.MARKER)
        if found is dotable.MARKER:
            raise AttributeError(key)
        return found

    def to_dict(self):
        return {k: v.to_dict() if isinstance(v, dotable) else v for k, v in self.items()}

    __setattr__ = __setitem__


subdict = lambda d, keys: {k: d[k] for k in keys if k in d}
