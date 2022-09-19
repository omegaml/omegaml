from omegaee import eedefaults as _base_config_ee

# initialize logging
import yaml
import logging.config

try:
    with open(getattr(_base_config_ee, 'OMEGA_LOGGING_CONFIG'), 'r') as fin:
        loggingConfig = yaml.safe_load(fin)
        _base_config_ee.LOGGING = loggingConfig.get('logging', loggingConfig)
except:
    pass

if hasattr(_base_config_ee, 'LOGGING'):
    try:
        logging.config.dictConfig(_base_config_ee.LOGGING)
    except Exception as e:
        logging.warning(f'could not initialize logging configuration due to {e}')
    logging.info('omegaml initialized')
