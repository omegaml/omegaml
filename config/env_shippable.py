import os

from config import EnvSettings_LocalTest


class EnvSettings_Shippable(EnvSettings_LocalTest):
    MONGO_PORT = os.environ.get('SHIPPABLE_MONGODB_PORT', '27017')

    BASE_MONGO_URL = 'mongodb://{user}:{password}@{mongohost}/{dbname}'
    MONGO_ADMIN_URL = BASE_MONGO_URL.format(user='admin',
                                            mongohost='localhost:{}'.format(
                                                MONGO_PORT),
                                            password='foobar',
                                            dbname='admin')

    OMEGA_MONGO_URL = BASE_MONGO_URL.format(user='admin',
                                            mongohost='localhost:{}'.format(
                                                MONGO_PORT),
                                            password='foobar',
                                            dbname='testdb')

    SITE_ID = 1

    CONSTANCE_CONFIG = {
        'MONGO_HOST': ('localhost:{}'.format(MONGO_PORT), 'mongo db host name'),
        'JYHUB_HOST': ('localhost:8888', 'jupyter hub public host name'),
        'BROKER_URL': ('amqp://guest@127.0.0.1:5672//', 'rabbitmq broker url'),
    }

    DEBUG = True
