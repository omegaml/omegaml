import json
import os
from urllib.parse import urlparse

from config.env_global import EnvSettingsGlobal
from stackable.contrib.config.conf_allauth import Config_DjangoAllAuth
from stackable.contrib.config.conf_bootstrap import Config_Bootstrap3
from stackable.contrib.config.conf_cities_light import Config_Cities_Light
from stackable.contrib.config.conf_constance import Config_DjangoConstance
from stackable.contrib.config.conf_djangoadmin import Config_DjangoAdmin
from stackable.contrib.config.conf_djangograppelli import Config_DjangoGrappelli
from stackable.contrib.config.conf_djangologging import Config_DjangoLogging
from stackable.contrib.config.conf_djangonose import Config_DjangoNoseTests
from stackable.contrib.config.conf_payment import Config_DjangoPayments
from stackable.contrib.config.conf_postoffice import Config_DjangoPostOffice
from stackable.contrib.config.conf_sekizai import Config_DjangoSekizai
from stackable.contrib.config.conf_whitenoise import Config_DjangoWhitenoise
from stackable.contrib.config.email.filebased import Config_FileEmail
from stackable.stackable import StackableSettings

truefalse = lambda v: (v if isinstance(v, bool) else
                       any(str(v).lower().startswith(c) for c in 'yt1'))


class EnvSettings_Local(Config_DjangoWhitenoise,
                        Config_DjangoNoseTests,
                        Config_DjangoSekizai,
                        Config_Bootstrap3,
                        Config_DjangoPayments,
                        Config_DjangoConstance,
                        Config_FileEmail,
                        Config_DjangoGrappelli,
                        #Config_Airbrake,
                        #Config_DebugToolbar,
                        Config_Cities_Light,
                        Config_DjangoAllAuth,
                        Config_DjangoAdmin,
                        Config_DjangoPostOffice,
                        Config_DjangoLogging,
                        # Config_DjangoDebugPermissions,
                        EnvSettingsGlobal):
    _prefix_apps = ('omegaweb', 'landingpage', 'paasdeploy', 'orders')
    _addl_apps = ('tastypie',
                  'tastypie_swagger',
                  'tastypiex',
                  'organizations',
                  'django_extensions',
                  )
    StackableSettings.patch_apps(_prefix_apps, at='django.contrib.staticfiles')
    StackableSettings.patch_apps(_addl_apps)

    _addl_middlewares = (
        'omegaweb.middleware.EventsLoggingMiddleware',
    )
    StackableSettings.patch_middleware(_addl_middlewares)

    API_CONFIG = {
        'omega_apis': (
            ('omegaweb', 'omegaweb.api.v1_api'),
        ),
        'admin_apis': (
            ('landingpage', 'landingpage.api.config.v2_auth_api'),
            ('paasdeploy', 'paasdeploy.api.config.v2_service_api'),
        )
    }

    BASE_MONGO_URL = 'mongodb://{mongouser}:{mongopassword}@{mongohost}/{mongodbname}'
    BASE_BROKER_URL = 'amqp://{brokeruser}:{brokerpassword}@{brokerhost}/{brokervhost}'

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

    SITE_ID = 1

    jyhub_host = os.environ.get('JYHUB_HOST', 'localhost:5000')
    broker_url = os.environ.get('BROKER_URL', 'amqp://guest:foobar@localhost:5672//')
    parsed = urlparse(broker_url)
    broker_host = os.environ.get('BROKER_HOST') or '{}:{}'.format(parsed.hostname, parsed.port)

    # TODO describe this in managed service docs
    # jupyter kubespawner and omegaml-worker pylibs
    # the default is to install the same pylib for all clients -- globally managed, only
    # management pods can update the storage
    # details see https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/V1Volume.md
    # * pvc-{username}-pylib-base maps to a cluster-wide nfs share in omegaml-services,
    # * pvc-{username}-pylib-user maps to a user-namespaced nfs share in the user's namespace
    #                             base is created in helmcharts/storage/033-pylib-pvc.yaml (global share)
    #                             user pvcs created in helmcharts/worker/060-pylib-user-pvc.yaml
    _default_cluster_storage = json.dumps({
        "volumes": [
            {
                "name": "pylib-base",
                "persistentVolumeClaim": {
                    "claimName": "pvc-omegaml-pylib-base-omegaml",
                    "readOnly": False
                }},
            {
                "name": "pylib-user",
                "persistentVolumeClaim": {
                    "claimName": "pvc-omegaml-pylib-user",
                    "readOnly": False
                }
            }
        ],
        "volumeMounts": [
            {
                "name": "pylib-base",
                "mountPath": "/app/pylib/base",
                "readOnly": True
            },
            {
                "name": "pylib-user",
                "mountPath": "/app/pylib/user",
                "readOnly": True
            }
        ]
    })
    # the omegaml defaults provided by runtime
    _default_omega_defaults = json.dumps({
        'OMEGA_FRAMEWORKS': ('scikit-learn', 'tensorflow', 'keras', 'dash'),
    })

    _default_jupyter_config_overrides = json.dumps({})

    jupyter_image = os.environ.get('OMEGA_JUPYTER_IMAGE', 'omegaml/omegaml-ee:latest')
    runtime_image = os.environ.get('OMEGA_RUNTIME_IMAGE', 'omegaml/omegaml-ee:latest')

    StackableSettings.patch_dict('CONSTANCE_CONFIG', {
        'MONGO_HOST': (mongo_host, 'mongo db host name'),
        'JYHUB_HOST': (jyhub_host, 'jupyter hub public host name'),
        'BROKER_URL': (broker_url, 'rabbitmq broker url (deprecated)'),
        'BROKER_HOST': (broker_host, 'rabbitmq broker host'),
        'JUPYTER_IMAGE': (jupyter_image, 'jupyter image'),
        'JUPYTER_AFFINITY_ROLE': ('worker', 'jupyter k8s affinity role'),
        'JUPYTER_NODE_SELECTOR': ('omegaml.io/role=worker', 'jupyter k8s node selector'),
        'JUPYTER_NAMESPACE': ('default', 'jupyter k8s cluster namespace'),
        'RUNTIME_IMAGE': (runtime_image, 'runtime image'),
        'RUNTIME_AFFINITY_ROLE': ('worker', 'runtime k8s affinity role'),
        'RUNTIME_NODE_SELECTOR': ('omegaml.io/role=worker', 'runtime k8s node selector'),
        'RUNTIME_NAMESPACE': ('default', 'runtime k8s cluster namespace'),
        'CLUSTER_STORAGE': (_default_cluster_storage, 'json cluster storage specs, applied to all services'),
        'OMEGA_DEFAULTS': (_default_omega_defaults, 'json omegaml defaults'),
        'JUPYTER_CONFIG': (_default_jupyter_config_overrides, 'json jupyter config overrides'),
    })

    DEBUG = truefalse(os.environ.get('DJANGO_DEBUG', False))

    ALLOWED_HOSTS = ['localhost', 'testserver']

    STATICFILES_STORAGE = 'omegaweb.util.FailsafeCompressedManifestStaticFilesStorage'

    OMEGA_JYHUB_URL = 'http://localhost:5000'
    OMEGA_JYHUB_USER = os.environ.get('OMEGA_JYHUB_USER', 'jyadmin')
    OMEGA_JYHUB_TOKEN = os.environ.get('OMEGA_JYHUB_TOKEN', '2a67924fa4a9782abe3dd23826a01401833a10f1')
    OMEGA_RESTAPI_URL = 'http://localhost:8000'

    OMEGA_CELERY_IMPORTS = ['omegaml.tasks',
                            'omegaml.notebook.tasks',
                            'omegaee.tasks',
                            'omegaml.backends.package.tasks']
    #: authentication environment
    OMEGA_AUTH_ENV = 'omegaml.client.auth.OmegaSecureAuthenticationEnv'

    # be compatible with omegaml-core flask API which does not allow trailing slash
    TASTYPIE_ALLOW_MISSING_SLASH = True
    APPEND_SLASH = True

    # stripe
    STRIPE_APIKEY = os.environ.get('STRIPE_APIKEY', 'invalid-token')
    STRIPE_REGISTER_ON_SIGNUP = (True if 'STRIPE_KEY' in os.environ
                                 else os.environ.get('STRIPE_REGISTER', False))

    # fernet encryption fields
    # https://django-fernet-fields.readthedocs.io/en/latest/#keys
    # specify FERNET_KEYS as "new:previous-1:previous-2" with the oldest being the last one
    # if you don't specify FERNET_KEYS env, SECRET_KEY will be used
    _fernet_keys = os.environ.get('FERNET_KEYS', '').split(':') + [EnvSettingsGlobal.SECRET_KEY]
    FERNET_KEYS = [k for k in _fernet_keys if k]
