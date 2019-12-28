import os

from config.env_local import EnvSettings_Local


class EnvSettings_LocalTest(EnvSettings_Local):
    NOSE_ARGS = ['--nologcapture', '-s']

    BASE_MONGO_URL = 'mongodb://{mongouser}:{mongopassword}@{mongohost}/{mongodbname}'
    mongo_host = os.environ.get('MONGO_HOST', 'localhost:27017')
    MONGO_ADMIN_URL = (os.environ.get('MONGO_ADMIN_URL') or
                       BASE_MONGO_URL.format(mongouser='admin',
                                             mongohost=mongo_host,
                                             mongopassword='foobar',
                                             mongodbname='admin'))

    OMEGA_MONGO_URL = (os.environ.get('OMEGA_MONGO_URL') or
                       os.environ.get('MONGO_URL') or
                       BASE_MONGO_URL.format(mongouser='admin',
                                             mongohost=mongo_host,
                                             mongopassword='foobar',
                                             mongodbname='userdb'))

    OMEGA_RESTAPI_URL = ''
    # allow default task auth for testing
    OMEGA_ALLOW_TASK_DEFAULT_AUTH = True


