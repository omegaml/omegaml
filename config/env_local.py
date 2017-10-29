import os
from stackable.contrib.config.conf_allauth import Config_DjangoAllAuth
from stackable.contrib.config.conf_bootstrap import Config_Bootstrap3
from stackable.contrib.config.conf_cities_light import Config_Cities_Light
from stackable.contrib.config.conf_djangoadmin import Config_DjangoAdmin
from stackable.contrib.config.conf_payment import Config_DjangoPayments
from stackable.contrib.config.conf_postoffice import Config_DjangoPostOffice
from stackable.contrib.config.conf_sekizai import Config_DjangoSekizai
from stackable.contrib.config.email.filebased import Config_FileEmail
from stackable.stackable import StackableSettings

from config.env_global import EnvSettingsGlobal

base_mongo_url = 'mongodb://{user}:{password}@localhost:27019/{dbname}'


class EnvSettings_Local(Config_DjangoSekizai,
                        Config_Bootstrap3,
                        Config_DjangoPayments,
                        Config_FileEmail,
                        Config_Cities_Light,
                        Config_DjangoAllAuth,
                        Config_DjangoAdmin,
                        Config_DjangoPostOffice,
                        EnvSettingsGlobal):
    _prefix_apps = ('landingpage',)
    _addl_apps = ('tastypie',
                  'tastypie_swagger',
                  'tastypiex',
                  'orders',
                  'organizations',
                  'django_extensions',
                  'omegaweb')
    StackableSettings.patch_apps(_prefix_apps, prepend=True)
    StackableSettings.patch_apps(_addl_apps)

    API_CONFIG = {
        'apis': (
            ('omegaweb', 'omegaweb.api.v1_api'),
        ),
    }

    MONGO_ADMIN_URL = base_mongo_url.format(user='admin',
                                            password='foobar',
                                            dbname='admin')
    MONGO_URL = os.environ.get('MONGO_URL')

    SITE_ID = 1
