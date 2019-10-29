from __future__ import absolute_import

import os

'''
make sure Celery is correctly configured
see http://chriskief.com/2013/11/15/celery-3-1-with-django-django-celery-rabbitmq-and-macports/
'''

from celery import Celery


def configure():
    # configure django and omega settings
    from django.conf import settings as djsettings
    from omegaml import settings as omsettings
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
    omsettings()


def start():
    from omegaops import opsdefaults
    # start celery
    app = Celery('omegaops')
    if opsdefaults.OMEGA_LOCAL_RUNTIME:
        opsdefaults.OMEGA_CLOUD_CELERY_CONFIG['CELERY_ALWAYS_EAGER'] = True
    app.config_from_object(opsdefaults.OMEGA_CLOUD_CELERY_CONFIG)
    app.autodiscover_tasks(opsdefaults.OMEGA_CLOUD_CELERY_IMPORTS)
    return app


configure()
app = start()
print("**** omegaops.celeryapp loaded")
