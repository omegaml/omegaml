def protected(kw):
    return '__' + kw


def get_omega(args):
    from omegaml import setup, _base_config
    from omegaml.client.cloud import setup_from_config
    config_file = args.get('--config')
    local_runtime = args.get('--local-runtime')
    if local_runtime:
        _base_config.OMEGA_LOCAL_RUNTIME = True
    bucket = args.get('--bucket')
    if config_file:
        om = setup_from_config(config_file)
    else:
        om = setup()
    return om[bucket]
