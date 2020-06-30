from __future__ import absolute_import

'''
make sure Celery is correctly configured
see http://chriskief.com/2013/11/15/celery-3-1-with-django-django-celery-rabbitmq-and-macports/
'''

import os

from celery import Celery
from omegaml import settings as omsettings

# get rid of celery's Django compatibility mode
os.environ['DJANGO_SETTINGS_MODULE'] = ''

try:
    import omegaml as om
    # see if we can get an instance from the configuration env
    om = om.setup()
    defaults = om.defaults
except:
    # otherwise just load local defaults
    defaults = omsettings()

app = Celery('omegaml')
app.config_from_object(defaults.OMEGA_CELERY_CONFIG)
app.autodiscover_tasks(defaults.OMEGA_CELERY_IMPORTS, related_name='tasks')
