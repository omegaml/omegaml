import os

from config import EnvSettings_LocalTest


class EnvSettings_Shippable(EnvSettings_LocalTest):
    MONGO_PORT = os.environ.get('SHIPPABLE_MONGODB_PORT', '27017')

    BASE_MONGO_URL = 'mongodb://{mongouser}:{mongopassword}@{mongohost}/{mongodbname}'
    MONGO_ADMIN_URL = BASE_MONGO_URL.format(mongouser='admin',
                                            mongohost='localhost:{}'.format(
                                                MONGO_PORT),
                                            mongopassword='jk3XVEpbpevN4BgtEbmcCpVM24gc7RVB',
                                            mongodbname='admin')

    OMEGA_MONGO_URL = BASE_MONGO_URL.format(mongouser='admin',
                                            mongohost='localhost:{}'.format(
                                                MONGO_PORT),
                                            mongopassword='foobar',
                                            mongodbname='testdb')

    SITE_ID = 1

    CONSTANCE_CONFIG = {
        'MONGO_HOST': ('localhost:{}'.format(MONGO_PORT), 'mongo db host name'),
        'JYHUB_HOST': ('localhost:8888', 'jupyter hub public host name'),
        'BROKER_URL': ('amqp://guest@127.0.0.1:5672//', 'rabbitmq broker url'),
        'JUPYTER_IMAGE': ('omegaml/omegaml-ee:latest', 'jupyter image'),
        'JUPYTER_AFFINITY_ROLE': ('worker', 'jupyter k8s affinity role'),
        'JUPYTER_NODE_SELECTOR': ('omegaml.io/role=worker', 'jupyter k8s node selector'),
        'JUPYTER_NAMESPACE': ('default', 'jupyter k8s cluster namespace'),
        'RUNTIME_IMAGE': ('omegaml/omegaml-ee:latest', 'runtime image'),
        'RUNTIME_AFFINITY_ROLE': ('worker', 'runtime k8s affinity role'),
        'RUNTIME_NODE_SELECTOR': ('omegaml.io/role=worker', 'runtime k8s node selector'),
        'RUNTIME_NAMESPACE': ('default', 'runtime k8s cluster namespace'),
    }

    DEBUG = True
