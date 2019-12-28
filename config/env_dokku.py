from stackable.contrib.config.conf_api import Config_ApiKeys
from stackable.contrib.config.conf_dokku import Config_Dokku
from .env_local import EnvSettings_Local


class EnvSettings_dokku(Config_Dokku,
                        Config_ApiKeys,
                        EnvSettings_Local):
    ALLOWED_HOSTS = ['omegaml.dokku.me', 'localhost']

    CONSTANCE_CONFIG = {
        'MONGO_HOST': ('dokku.me:27017', 'mongo db public host name'),
        'JYHUB_HOST': ('dokku.me:8899', 'jupyter hub public host name'),
        'BROKER_URL': ('amqp://guest@dokku.me:5672//',
                       'rabbitmq broker url'),
        'JUPYTER_IMAGE': ('omegaml/omegaml-ee:latest', 'jupyter image'),
        'JUPYTER_AFFINITY_ROLE': ('worker', 'jupyter k8s affinity role'),
        'JUPYTER_NODE_SELECTOR': ('omegaml.io/role=worker', 'jupyter k8s node selector'),
        'JUPYTER_NAMESPACE': ('default', 'jupyter k8s cluster namespace'),
        'RUNTIME_IMAGE': ('omegaml/omegaml-ee:latest', 'runtime image'),
        'RUNTIME_AFFINITY_ROLE': ('worker', 'runtime k8s affinity role'),
        'RUNTIME_NODE_SELECTOR': ('omegaml.io/role=worker', 'runtime k8s node selector'),
        'RUNTIME_NAMESPACE': ('default', 'runtime k8s cluster namespace'),
    }
