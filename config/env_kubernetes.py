import os

from stackable.contrib.config.conf_api import Config_ApiKeys
from stackable.contrib.config.conf_dokku import Config_Dokku
from .env_local import EnvSettings_Local


class EnvSettings_kubernetes(Config_Dokku,
                             Config_ApiKeys,
                             EnvSettings_Local):
    ALLOWED_HOSTS = ['omegaml.me', 'localhost', 'omegaml']

    CONSTANCE_CONFIG = {
        'MONGO_HOST': ('localhost:27017', 'mongo db public host name'),
        'JYHUB_HOST': ('localhost:8888', 'jupyter hub public host name'),
        'BROKER_URL': ('amqp://rabbitmq:5672//',
                       'rabbitmq broker url'),
        'CELERY_ALWAYS_EAGER': (False, 'if True celery tasks are processed locally'),
    }

    BASE_MONGO_URL = 'mongodb://{user}:{password}@{mongohost}/{dbname}'
    MONGO_ADMIN_URL = (os.environ.get('MONGO_ADMIN_URL') or
                       BASE_MONGO_URL.format(user='admin',
                                             mongohost='mongodb',
                                             password='foobar',
                                             dbname='admin'))

    OMEGA_MONGO_URL = (os.environ.get('MONGO_URL') or
                       BASE_MONGO_URL.format(user='user',
                                             mongohost='mongodb',
                                             password='foobar',
                                             dbname='userdb'))

    OMEGA_JYHUB_URL = os.environ.get('OMEGA_JYHUB_URL', 'http://omjobs:5000')
    OMEGA_JYHUB_USER = os.environ.get('OMEGA_JYHUB_USER', 'jyadmin')
    OMEGA_JYHUB_TOKEN = os.environ.get('OMEGA_JYHUB_TOKEN', 'PQZ4Sw2YNvNpdnwbLetbDDDF6NcRbazv2dCL')
    OMEGA_RESTAPI_URL = os.environ.get('OMEGA_RESTAPI_URL', 'http://omegaweb:5000')

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('MYSQL_DATABASE', 'omegaml'),
            'USER': os.environ.get('MYSQL_USER', 'omegaml'),
            'PASSWORD': os.environ.get('MYSQL_PASSWORD', 'foobar'),
            'HOST': 'mysql',  # Or an IP Address that your DB is hosted on
            'PORT': '3306',
        }
    }
