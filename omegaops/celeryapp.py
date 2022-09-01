from __future__ import absolute_import

import os

'''
make sure Celery is correctly configured
see http://chriskief.com/2013/11/15/celery-3-1-with-django-django-celery-rabbitmq-and-macports/
'''
from celery import Celery


def configure():
    # configure django and omega settings
    from omegaml import settings as omsettings, _base_config
    from omegaops import opsdefaults
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
    try:
        # see if we can get an instance from the configuration env
        import omegaml as om
        om = om.setup()
        defaults = om.defaults
    except:
        # otherwise just load local defaults
        defaults = omsettings()
    _base_config.update_from_obj(opsdefaults, attrs=defaults)
    return defaults


def start(opsdefaults):
    # start celery
    app = Celery('omegaops')
    if opsdefaults.OMEGA_LOCAL_RUNTIME:
        opsdefaults.OMEGA_CELERY_CONFIG['CELERY_ALWAYS_EAGER'] = True
    app.config_from_object(opsdefaults.OMEGA_CELERY_CONFIG)
    app.autodiscover_tasks(opsdefaults.OMEGA_CELERY_IMPORTS)
    app.finalize()
    return app


defaults = configure()
app = start(defaults)
print("**** omegaops.celeryapp loaded")
