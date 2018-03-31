from stackable.contrib.config.conf_dokku import Config_Dokku

from .env_local import EnvSettings_Local
from stackable.contrib.config.conf_api import Config_ApiKeys
from stackable.contrib.config.conf_whitenoise import Config_DjangoWhitenoise


class EnvSettings_omegamlio(Config_Dokku,
                            Config_ApiKeys,
                            Config_DjangoWhitenoise,
                            EnvSettings_Local):
    ALLOWED_HOSTS = ['omegaml.omegaml.io']

    CONSTANCE_CONFIG = {
        'MONGO_HOST': ('omegaml.omegaml.io:27017', 'mongo db host name'),
        'BROKER_URL': ('amqp://guest@omegaml.omegaml.io:5672//',
                       'rabbitmq broker url'),
        'CELERY_ALWAYS_EAGER': (False, 'if True celery tasks are processed locally'),
    }
