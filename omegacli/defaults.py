#: the omegaweb url
import os
OMEGA_RESTAPI_URL = os.environ.get('OMEGA_RESTAPI_URL',
                                   'http://omegaml.dokku.me/')
