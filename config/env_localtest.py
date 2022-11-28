import os

from config.conf_jwtauth import Config_OmegaJWTAuth
from config.env_local import EnvSettings_Local
from stackable import StackableSettings
from stackable.contrib.config.conf_teamcity import Config_TeamcityTests


class EnvSettings_LocalTest(Config_TeamcityTests,
                            Config_OmegaJWTAuth,
                            EnvSettings_Local):
    NOSE_ARGS = '--nologcapture --verbosity 2 -s'.split(' ')

    BASE_MONGO_URL = 'mongodb://{mongouser}:{mongopassword}@{mongohost}/{mongodbname}'
    mongo_host = os.environ.get('MONGO_HOST', 'localhost:27017')
    MONGO_ADMIN_URL = (os.environ.get('MONGO_ADMIN_URL') or
                       BASE_MONGO_URL.format(mongouser='admin',
                                             mongohost=mongo_host,
                                             mongopassword='jk3XVEpbpevN4BgtEbmcCpVM24gc7RVB',
                                             mongodbname='admin'))

    OMEGA_MONGO_URL = (os.environ.get('OMEGA_MONGO_URL') or
                       os.environ.get('MONGO_URL') or
                       BASE_MONGO_URL.format(mongouser='admin',
                                             mongohost=mongo_host,
                                             mongopassword='jk3XVEpbpevN4BgtEbmcCpVM24gc7RVB',
                                             mongodbname='userdb'))

    # force use of test client
    OMEGA_RESTAPI_URL = ''
    # allow default task auth for testing
    OMEGA_ALLOW_TASK_DEFAULT_AUTH = True
    # allow signup via api
    ALLAUTH_ALLOW_API_SIGNUP = True

    # switch off stripe customer registration in landingpage
    STRIPE_REGISTER_ON_SIGNUP = False

    # no session cache to avoid test failures on repeated tests
    OMEGA_SESSION_CACHE = {
        'maxsize': 0,
        'ttl': 0.1,
    }

    # patch celery imports so existing imports elsewhere are kept
    _celery_imports = ['omegaops']
    StackableSettings.patch_list('OMEGA_CELERY_IMPORTS', _celery_imports)

    # test settings
    # -- django jwtauth uses username instead of preferred_username
    JWT_PAYLOAD_USERNAME_KEY = 'username'

    # enable test mode
    # -- compatibility with landingpage.secretsvault
    TEST_MODE = True
    # -- omegaml runtime
    OMEGA_LOCAL_RUNTIME = True

