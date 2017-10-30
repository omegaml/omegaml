from stackable.contrib.config.conf_dokku import Config_Dokku

from .env_local import EnvSettings_Local
from stackable.contrib.config.conf_api import Config_ApiKeys


class EnvSettings_dokku(Config_Dokku,
                        Config_ApiKeys,
                        EnvSettings_Local):
    ALLOWED_HOSTS = ['omegaml.dokku.me']
