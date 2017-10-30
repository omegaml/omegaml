import json
from landingpage.models import ServiceDeployment, ServicePlan
import os

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
    _admin_newdb.add_user(username, password, roles=roles)
    # we need to get the newdb from the client otherwise
    # newdb has admin rights (!)
    client_mongo_url = settings.BASE_MONGO_URL.format(user=username,
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
    settings = user.services.get(offering__name='omegaml').settings
    mongo_url = settings.BASE_MONGO_URL.format(**settings)
    # FIXME get amqp from env
    client_config = {
        "OMEGA_CELERY_CONFIG": {
            "CELERY_MONGODB_BACKEND_SETTINGS": {
                "taskmeta_collection": "omegaml_taskmeta",
                "database": mongo_url,
            },
            "CELERY_ACCEPT_CONTENT": [
                "pickle",
                "json",
                "msgpack",
                "yaml"
            ]
        },
        "OMEGA_MONGO_URL": mongo_url,
        "OMEGA_RESULT_BACKEND": mongo_url,
        "OMEGA_NOTEBOOK_COLLECTION": "ipynb",
        "OMEGA_TMP": "/tmp",
        "OMEGA_MONGO_COLLECTION": "omegaml",
        "OMEGA_BROKER": "amqp://guest@127.0.0.1:5672//"
    }
    return client_config
