import os

from config.env_local import EnvSettings_Local
from stackable import stackable, StackableSettings


class EnvSettings_LocalTest(EnvSettings_Local):
    NOSE_ARGS = ['--nologcapture', '-s']

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

    OMEGA_RESTAPI_URL = ''
    # allow default task auth for testing
    OMEGA_ALLOW_TASK_DEFAULT_AUTH = True


