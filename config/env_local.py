import os

from config.env_global import EnvSettingsGlobal
from stackable.contrib.config.conf_allauth import Config_DjangoAllAuth
from stackable.contrib.config.conf_bootstrap import Config_Bootstrap3
from stackable.contrib.config.conf_cities_light import Config_Cities_Light
from stackable.contrib.config.conf_constance import Config_DjangoConstance
from stackable.contrib.config.conf_djangoadmin import Config_DjangoAdmin
from stackable.contrib.config.conf_djangonose import Config_DjangoNoseTests
from stackable.contrib.config.conf_payment import Config_DjangoPayments
from stackable.contrib.config.conf_postoffice import Config_DjangoPostOffice
from stackable.contrib.config.conf_sekizai import Config_DjangoSekizai
from stackable.contrib.config.conf_whitenoise import Config_DjangoWhitenoise
from stackable.contrib.config.email.filebased import Config_FileEmail
from stackable.stackable import StackableSettings


class EnvSettings_Local(Config_DjangoWhitenoise,
                        Config_DjangoNoseTests,
                        Config_DjangoSekizai,
                        Config_Bootstrap3,
                        Config_DjangoPayments,
                        Config_DjangoConstance,
                        Config_FileEmail,
                        # Config_DebugToolbar,
                        Config_Cities_Light,
                        Config_DjangoAllAuth,
                        Config_DjangoAdmin,
                        Config_DjangoPostOffice,
                        EnvSettingsGlobal):
    _prefix_apps = ('omegaweb', 'landingpage', 'paasdeploy', 'orders')
    _addl_apps = ('tastypie',
                  'tastypie_swagger',
                  'tastypiex',
                  'organizations',
                  'django_extensions',
                  )
    StackableSettings.patch_apps(_prefix_apps, at='django.contrib.staticfiles')
    StackableSettings.patch_apps(_addl_apps)

    API_CONFIG = {
        'apis': (
            ('omegaweb', 'omegaweb.api.v1_api'),
        ),
    }

    BASE_MONGO_URL = 'mongodb://{user}:{password}@{mongohost}/{dbname}'

    mongo_host = os.environ.get('MONGO_HOST', 'localhost:27017')
    MONGO_ADMIN_URL = (os.environ.get('MONGO_ADMIN_URL') or
                       BASE_MONGO_URL.format(user='admin',
                                            mongohost=mongo_host,
                                            password='foobar',
                                            dbname='admin'))

    OMEGA_MONGO_URL = (os.environ.get('OMEGA_MONGO_URL') or
                       os.environ.get('MONGO_URL') or
                       BASE_MONGO_URL.format(user='admin',
                                             mongohost=mongo_host,
                                             password='foobar',
                                             dbname='userdb'))

    SITE_ID = 1

    jyhub_host = os.environ.get('JYHUB_HOST', 'localhost:5000')
    broker_url = os.environ.get('BROKER_URL', 'amqp://localhost:5672//')

    CONSTANCE_CONFIG = {
        'MONGO_HOST': (mongo_host, 'mongo db host name'),
        'JYHUB_HOST': (jyhub_host, 'jupyter hub public host name'),
        'BROKER_URL': (broker_url, 'rabbitmq broker url'),
    }

    DEBUG = os.environ.get('DJANGO_DEBUG', False)

    ALLOWED_HOSTS = ['localhost', 'testserver']

    STATICFILES_STORAGE = 'omegaweb.util.FailsafeCompressedManifestStaticFilesStorage'

    OMEGA_JYHUB_URL = 'http://localhost:5000'
    OMEGA_JYHUB_USER = os.environ.get('OMEGA_JYHUB_USER', 'jyadmin')
    OMEGA_JYHUB_TOKEN = os.environ.get('OMEGA_JYHUB_TOKEN', '2a67924fa4a9782abe3dd23826a01401833a10f1')
    OMEGA_RESTAPI_URL = 'http://localhost:8000'

    OMEGA_CELERY_IMPORTS = ['omegaml.tasks', 'omegaml.notebook.tasks', 'omegaee.tasks', 'omegapkg.tasks']
    #: authentication environment
    OMEGA_AUTH_ENV = 'omegacommon.auth.OmegaSecureAuthenticationEnv'

    # be compatible with omegaml-core flask API which does not allow trailing slash
    TASTYPIE_ALLOW_MISSING_SLASH = True