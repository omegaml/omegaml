import os

from config.conf_anymail import Config_Anymail
from stackable import StackableSettings
from stackable.contrib.config.conf_api import Config_ApiKeys
from stackable.contrib.config.conf_dokku import Config_Dokku

from .env_local import EnvSettings_Local


class EnvSettings_omegamlio(Config_Dokku,
                            Config_ApiKeys,
                            Config_Anymail,
                            EnvSettings_Local):
    # django
    ALLOWED_HOSTS = ['omegaml.omegaml.io']
    DEBUG = False
    # constance
    CONSTANCE_CONFIG = {
        'MONGO_HOST': ('omegaml.omegaml.io:27017', 'mongo db host name'),
        'JYHUB_HOST': ('omjobs.omegaml.io', 'jupyter hub public host name'),
        'BROKER_URL': ('amqp://guest@omegaml.omegaml.io:5672//',
                       'rabbitmq public broker url'),
    }
    # jupyerhub settings
    OMEGA_JYHUB_URL = 'http://omjobs.omegaml.io'
    OMEGA_JYHUB_USER = os.environ.get('OMEGA_JYHUB_USER')
    OMEGA_JYHUB_TOKEN = os.environ.get('OMEGA_JYHUB_TOKEN')
