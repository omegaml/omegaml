from __future__ import absolute_import

from omegaml import settings
from omegaops import opsdefaults

'''
make sure Celery is correctly configured
see http://chriskief.com/2013/11/15/celery-3-1-with-django-django-celery-rabbitmq-and-macports/
'''

from celery import Celery

settings()
app = Celery('omegaml-cloudmgr')
app.config_from_object(opsdefaults.OMEGA_CLOUD_CELERY_CONFIG)
app.autodiscover_tasks(opsdefaults.OMEGA_CLOUD_CELERY_IMPORTS)
