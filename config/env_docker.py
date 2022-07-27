import os

from stackable.contrib.config.conf_api import Config_ApiKeys
from stackable.contrib.config.conf_dokku import Config_Dokku
from .env_local import EnvSettings_Local


class EnvSettings_docker(Config_Dokku,
                         Config_ApiKeys,
                         EnvSettings_Local):
    # must match docker-compose configuration
    ALLOWED_HOSTS = ['localhost', 'omegaweb', 'omegaml']

    if 'DATABASE_URL' not in os.environ:
        if 'MYSQL_USER' in os.environ:
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
        elif 'POSTGRES_USER' in os.environ:
            DATABASES = {
                'default': {
                    'ENGINE': 'django.db.backends.postgresql',
                    'NAME': os.environ.get('POSTGRES_DATABASE', 'omegaml'),
                    'USER': os.environ.get('POSTGRES_USER', 'omegaml'),
                    'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'foobar'),
                    'HOST': 'postgres',  # Or an IP Address that your DB is hosted on
                    'PORT': '5432',
                }
            }
        else:
            # default to whatever default is configured (usually sqlite database)
            pass

    # optional = do not require account email verification
    # mandatory = verification email will be sent out
    # see https://django-allauth.readthedocs.io/en/latest/configuration.html
    ACCOUNT_EMAIL_VERIFICATION = 'mandatory'

    # set mongo admin url
    MONGO_ADMIN_URL = os.environ.get('MONGO_ADMIN_URL')
