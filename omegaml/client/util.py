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
        except:
            msg = ('Config file could not be found. Specify as --config or set '
                   'OMEGA_CONFIG_FILE env variable')
            raise ValueError(msg)
    else:
        om = setup()
    if local:
        om.runtime.mode(local=True)
    return om[bucket] if bucket else om # for speed


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self
