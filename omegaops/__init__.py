import json
from landingpage.models import ServiceDeployment, ServicePlan
import os

from constance import config
from django.conf import settings
from pymongo.mongo_client import MongoClient

def add_user(dbname, username, password):
    """
    add a user to omegaml giving readWrite access rights

    only this user will have access r/w rights to the database.
    """
    roles = [{
        'role': 'readWrite',
        'db': dbname,
    }]
    # create the db but NEVER return this db. it will have admin rights.
    client = MongoClient(settings.MONGO_ADMIN_URL)
    _admin_newdb = client[dbname]
    # add user and reset password in case the user was there already
    _admin_newdb.add_user(username, password, roles=roles)
    _admin_newdb.command("updateUser", username, pwd=password)
    # we need to get the newdb from the client otherwise
    # newdb has admin rights (!)
    mongohost = config.MONGO_HOST
    client_mongo_url = settings.BASE_MONGO_URL.format(user=username,
                                                      mongohost=mongohost,
                                                      password=password,
                                                      dbname=dbname)
    client = MongoClient(client_mongo_url)
    newdb = client[dbname]
    return newdb, client_mongo_url


def add_service_deployment(user, config):
    """
    add the service deployment
    """
    plan = ServicePlan.objects.get(name='omegaml')
    text = 'userid {user.username}<br>apikey {user.api_key.key}'.format(
        **locals())
    user.services.create(user=user,
                         text=text,
                         offering=plan,
                         settings=config)


def get_client_config(user):
    """
    return the full client configuration
    """
    import omegaml as om
    user_settings = user.services.get(offering__name='omegaml').settings
    user_settings['user'] = user_settings.get(
        'username') or user_settings.get('user')

    mongo_url = settings.BASE_MONGO_URL.format(mongohost=config.MONGO_HOST,
                                               **user_settings)
    # FIXME permission user instead of standard
    broker_url = config.BROKER_URL
    client_config = {
        "OMEGA_CELERY_CONFIG": {
            "BROKER_URL": broker_url,
            "CELERY_RESULT_BACKEND": 'amqp',
            "CELERY_ACCEPT_CONTENT": [
                "pickle",
                "json",
                "msgpack",
                "yaml"
            ]
        },
        "OMEGA_MONGO_URL": mongo_url,
        "OMEGA_NOTEBOOK_COLLECTION": om.defaults.OMEGA_NOTEBOOK_COLLECTION,
        "OMEGA_TMP": "/tmp",
        "OMEGA_MONGO_COLLECTION": "omegaml",
    }
    if config.CELERY_ALWAYS_EAGER:
        client_config['OMEGA_CELERY_CONFIG']['CELERY_ALWAYS_EAGER'] = True
    return client_config
