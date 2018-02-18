from stackable.contrib.config.conf_dokku import Config_Dokku

from .env_local import EnvSettings_Local
from stackable.contrib.config.conf_api import Config_ApiKeys
from stackable.contrib.config.conf_whitenoise import Config_DjangoWhitenoise


class EnvSettings_dokku(Config_Dokku,
                        Config_ApiKeys,
                        Config_DjangoWhitenoise,
                        EnvSettings_Local):
    ALLOWED_HOSTS = ['omegaml.dokku.me', 'localhost']

    CONSTANCE_CONFIG = {
        'MONGO_HOST': ('localhost:27019', 'mongo db host name'),
        'BROKER_URL': ('amqp://guest@dokku.me:5672//',
                       'rabbitmq broker url'),
        'CELERY_ALWAYS_EAGER': (False, 'if True celery tasks are processed locally'),
    }
