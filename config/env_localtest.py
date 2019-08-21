import os

from config.env_local import EnvSettings_Local


class EnvSettings_LocalTest(EnvSettings_Local):
    NOSE_ARGS = ['--nologcapture', '-s']

    BASE_MONGO_URL = 'mongodb://{user}:{password}@{mongohost}/{dbname}'
    MONGO_ADMIN_URL = BASE_MONGO_URL.format(user='admin',
                                            mongohost='localhost:27019',
                                            password='foobar',
                                            dbname='admin')

    OMEGA_MONGO_URL = (os.environ.get('MONGO_URL') or
                       BASE_MONGO_URL.format(user='admin',
                                             mongohost='localhost:27019',
                                             password='foobar',
                                             dbname='testdb'))

    OMEGA_RESTAPI_URL = ''
    # allow default task auth for testing
    OMEGA_ALLOW_TASK_DEFAULT_AUTH = True


