"""
WSGI config for x project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/howto/deployment/wsgi/
"""
import warnings

import os
from stackable import DjangoStackableSettings

# omegaweb should always be started without a security context USERID/APIKEY since:
# - it is the "top level" authenticator to clients that are started with security
# - if it starts with a security context, it will enter endless recursion
# - Also see manage.py
if any(k in os.environ for k in ('OMEGA_USERID', 'OMEGA_APIKEY')):
    warnings.warn('omegaweb ignores OMEGA_USERID/OMEGA_APIKEY found in env')
    os.environ.pop('OMEGA_USERID', None)
    os.environ.pop('OMEGA_APIKEY', None)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
application = DjangoStackableSettings.get_wsgi_application()

if os.environ.get('DJANGO_DEBUG', '0') in ('1', 'yes', 'true'):
    # debug gunicorn worker timeouts
    # https://stackoverflow.com/a/65438492/890242
    import faulthandler
    faulthandler.enable()
