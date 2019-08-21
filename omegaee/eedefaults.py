"""
Enterprise Edition defaults
"""
import os

#: storage backends
OMEGA_STORE_BACKENDS = {
    'sklearn.joblib': 'omegaml.backends.ScikitLearnBackend',
    'spark.mllib': 'omegaee.backends.SparkBackend',
    'pandas.csv': 'omegaee.backends.PandasExternalData',
    'python.package': 'omegapkg.PythonPackageData',
}
#: runtimes mixins
OMEGA_RUNTIME_MIXINS = [
    'omegaee.runtimes.mixins.AuthenticatedModelMixin',
    'omegaee.runtimes.mixins.AuthenticatedGridSearchMixin',
]

#: the omegaweb url
OMEGA_RESTAPI_URL = (os.environ.get('OMEGA_RESTAPI_URL') or
                     'http://localhost:8000')
#: omega user id
OMEGA_USERID = os.environ.get('OMEGA_USERID')
#: omega apikey
OMEGA_APIKEY = os.environ.get('OMEGA_APIKEY')

#: omega authentication provider
OMEGA_AUTH_ENV = 'omegacommon.auth.OmegaSecureAuthenticationEnv'
#: jupyterhub admin user (equals omegajobs.jupyter_config:c.JupyterHub.api_tokens)
OMEGA_JYHUB_USER = os.environ.get('OMEGA_JYHUB_USER', 'jyadmin')
#: jupyterhub admin token (equals omegajobs.jupyter_config:c.JupyterHub.api_tokens)
OMEGA_JYHUB_TOKEN = os.environ.get('OMEGA_JYHUB_TOKEN', 'PQZ4Sw2YNvNpdnwbLetbDDDF6NcRbazv2dCL')
#: jupyterhub url (port equals omegajobs.jupyter_config:c.JupyterHub.hub_port)
OMEGA_JYHUB_URL = os.environ.get('OMEGA_JYHUB_URL', 'http://localhost:8001')
#: omegaweb's API key user by JYHUB_USER to get another users config. Use omsetupuser to set this key
OMEGA_JYHUB_APIKEY = os.environ.get('OMEGA_JYHUB_APIKEY', 'b7b034f57d442e605ab91f88a8936149e968e12e')
#: allow a task to use the local default configuration (potentially insecure)
OMEGA_ALLOW_TASK_DEFAULT_AUTH=False

#: authentication environment
OMEGA_AUTH_ENV = 'omegacommon.auth.OmegaSecureAuthenticationEnv'