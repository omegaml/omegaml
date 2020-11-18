import os

from config.conf_anymail import Config_Anymail
from stackable.contrib.config.conf_api import Config_ApiKeys
from stackable.contrib.config.conf_dokku import Config_Dokku
from .env_local import EnvSettings_Local


class EnvSettings_kubernetes(Config_Dokku,
                             Config_ApiKeys,
                             Config_Anymail,
                             #Config_Airbrake,
                             EnvSettings_Local):
    _allowed_hosts = 'omegaml.me,localhost,omegaml'
    ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', _allowed_hosts).split(',')

    BASE_MONGO_URL = 'mongodb://{mongouser}:{mongopassword}@{mongohost}/{mongodbname}'
    MONGO_ADMIN_URL = (os.environ.get('MONGO_ADMIN_URL') or
                       BASE_MONGO_URL.format(mongouser='admin',
                                             mongohost='mongodb',
                                             mongopassword='foobar',
                                             mongodbname='admin'))

    OMEGA_MONGO_URL = (os.environ.get('OMEGA_MONGO_URL') or
                       BASE_MONGO_URL.format(mongouser='user',
                                             mongohost='mongodb',
                                             mongopassword='foobar',
                                             mongodbname='userdb'))

    OMEGA_JYHUB_URL = os.environ.get('OMEGA_JYHUB_URL', 'http://omjobs:5000')
    OMEGA_JYHUB_USER = os.environ.get('OMEGA_JYHUB_USER', 'jyadmin')
    OMEGA_JYHUB_TOKEN = os.environ.get('OMEGA_JYHUB_TOKEN', 'PQZ4Sw2YNvNpdnwbLetbDDDF6NcRbazv2dCL')
    OMEGA_RESTAPI_URL = os.environ.get('OMEGA_RESTAPI_URL', 'http://omegaml:5000')

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

    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')



