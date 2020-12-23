def protected(kw):
    return '__' + kw


def get_omega(args):
    from omegaml import setup, _base_config
    from omegaml.client.cloud import setup_from_config
    config_file = args.get('--config')
    # deprecated, use --local
    local_runtime = args.get('--local-runtime')
    local = args.get('--local')
    if local or local_runtime:
        _base_config.OMEGA_LOCAL_RUNTIME = True
    bucket = args.get('--bucket')
    if config_file:
        om = setup_from_config(config_file)
    else:
        om = setup()
    if local:
        om.runtime.mode(local=True)
    return om[bucket]


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self
