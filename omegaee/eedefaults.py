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

#: the omegaweb url
OMEGA_RESTAPI_URL = (os.environ.get('OMEGA_RESTAPI_URL') or
                     'http://localhost:8000')
#: omega user id
OMEGA_USERID = os.environ.get('OMEGA_USERID')
#: omega apikey
OMEGA_APIKEY = os.environ.get('OMEGA_APIKEY')

#: jupyterhub admin user (equals omegajobs.jupyter_config:c.JupyterHub.api_tokens)
OMEGA_JYHUB_USER = os.environ.get('OMEGA_JYHUB_USER', 'jyadmin')
#: jupyterhub admin token (equals omegajobs.jupyter_config:c.JupyterHub.api_tokens)
OMEGA_JYHUB_TOKEN = os.environ.get('OMEGA_JYHUB_TOKEN', 'PQZ4Sw2YNvNpdnwbLetbDDDF6NcRbazv2dCL')
#: jupyterhub url (port equals omegajobs.jupyter_config:c.JupyterHub.hub_port)
OMEGA_JYHUB_URL = os.environ.get('OMEGA_JYHUB_URL', 'http://localhost:8001')
#: omegaweb's API key user by JYHUB_USER to get another users config. Use omsetupuser to set this key
OMEGA_JYHUB_APIKEY = os.environ.get('OMEGA_JYHUB_APIKEY', 'f55750fff7d9ae6c20d5f46a41933f09ba5812a4')
