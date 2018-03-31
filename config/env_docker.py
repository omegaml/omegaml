import os
from stackable.contrib.config.conf_api import Config_ApiKeys
from stackable.contrib.config.conf_dokku import Config_Dokku
from stackable.contrib.config.conf_whitenoise import Config_DjangoWhitenoise

from .env_local import EnvSettings_Local


class EnvSettings_docker(Config_Dokku,
                         Config_ApiKeys,
                         EnvSettings_Local):
    # must match docker-compose configuration
    ALLOWED_HOSTS = ['localhost', 'omegaweb', 'omegaml']

    CONSTANCE_CONFIG = {
        'MONGO_HOST': ('mongodb', 'mongo db host name'),
        'BROKER_URL': ('amqp://rabbitmq//',
                       'rabbitmq broker url'),
        'CELERY_ALWAYS_EAGER': (False, 'if True celery tasks are processed locally'),
    }

    if 'MYSQL_ROOT_USER' in os.environ:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.mysql',
                'NAME': os.environ.get('MYSQL_DATABASE'),
                'USER': os.environ.get('MYSQL_USER'),
                'PASSWORD': os.environ.get('MYSQL_PASSWORD'),
                'HOST': 'mysql',
                'PORT': 3306,
            }
        }
    else:
        # default to whatever default is configured (usually sqlite database)
        pass

    # do not require account email verification
    ACCOUNT_EMAIL_VERIFICATION = 'optional'

    # set mongo admin url
    MONGO_ADMIN_URL = os.environ.get('MONGO_ADMIN_URL')
