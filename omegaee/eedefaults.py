"""
Enterprise Edition defaults
"""
import os

import sys
from os.path import basename

# determine how we're run
from urllib.parse import urlparse

is_cli_run = os.path.basename(sys.argv[0]) == 'om'
is_test_run = any(m in [basename(arg) for arg in sys.argv]
                  for m in ('unittest', 'test', 'nosetests', 'noserunner', '_jb_unittest_runner.py',
                            '_jb_nosetest_runner.py'))

#: the omegaweb url
OMEGA_RESTAPI_URL = (os.environ.get('OMEGA_RESTAPI_URL') or
                     'http://localhost:8000')
#: omega user id
OMEGA_USERID = os.environ.get('OMEGA_USERID')
#: omega apikey
OMEGA_APIKEY = os.environ.get('OMEGA_APIKEY')

#: omega authentication provider
OMEGA_AUTH_ENV = 'omegaml.client.auth.OmegaSecureAuthenticationEnv'
#: jupyterhub admin user (equals omegajobs.jupyter_config:c.JupyterHub.api_tokens)
OMEGA_JYHUB_USER = os.environ.get('OMEGA_JYHUB_USER', 'jyadmin')
#: jupyterhub admin token (equals omegajobs.jupyter_config:c.JupyterHub.api_tokens)
OMEGA_JYHUB_TOKEN = os.environ.get('OMEGA_JYHUB_TOKEN', 'PQZ4Sw2YNvNpdnwbLetbDDDF6NcRbazv2dCL')
#: jupyterhub url (port equals omegajobs.jupyter_config:c.JupyterHub.hub_port)
OMEGA_JYHUB_URL = os.environ.get('OMEGA_JYHUB_URL', 'http://localhost:8001')
#: omegaweb's API key user by JYHUB_USER to get another users config. Use omsetupuser to set this key
OMEGA_JYHUB_APIKEY = os.environ.get('OMEGA_JYHUB_APIKEY', 'b7b034f57d442e605ab91f88a8936149e968e12e')
#: allow a task to use the local default configuration (potentially insecure)
OMEGA_ALLOW_TASK_DEFAULT_AUTH = os.environ.get('OMEGA_ALLOW_TASK_DEFAULT_AUTH', False)
#: is the worker considered inside the same cluster as the client
OMEGA_WORKER_INCLUSTER = True

#: imports that the celery runtime will load dynamically
OMEGA_CELERY_IMPORTS = ['omegaml',
                        'omegaee',
                        'omegaml.notebook',
                        'omegaml.backends.package']
#: determine if we should use SSL for mongodb and rabbitmq
OMEGA_USESSL = True if os.environ.get('OMEGA_USESSL') else False
#: additional SSL kwargs for mongodb SSL connections
OMEGA_MONGO_SSL_KWARGS = {
    'ssl': OMEGA_USESSL,
    'ssl_ca_certs': os.environ.get('CA_CERTS_PATH') or None,
}
#: admin broker
OMEGA_BROKERAPI_URL = (os.environ.get('OMEGA_BROKERAPI_URL') or
                       'http://admin:een53uGa8Lvc9mKsyMyXtzH5pAMfD3FP@localhost:15672')
parsed = urlparse(OMEGA_BROKERAPI_URL)
port = 5671 if OMEGA_USESSL else 5672
OMEGA_BROKER_HOST = '{}:{}'.format(parsed.hostname, port)

