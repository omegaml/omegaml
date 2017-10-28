from stackable.contrib.config.conf_dokku import Config_Dokku

from .env_local import EnvSettings_Local


class EnvSettings_dokku(Config_Dokku,
                        EnvSettings_Local):
    ALLOWED_HOSTS = ['omegaml.dokku.me']
