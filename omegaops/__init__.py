import json
from landingpage.models import ServiceDeployment, ServicePlan
import os

from pymongo.mongo_client import MongoClient


def add_user(dbname, username, password):
    """
    add a user to omegaml giving readWrite access rights

    only this user will have access r/w rights to the database.
    """
    roles = roles = [{
        'role': 'readWrite',
        'db': dbname,
    }]
    # create the db but NEVER return this db. it will have admin rights.
    # TODO move admin db, user, password to secure settings
    MONGO_URL = os.environ.get('MONGO_URL',
                               'mongodb://{user}:{password}@localhost:27019/{dbname}')

    client = MongoClient(MONGO_URL.format(user='admin',
                                          password='foobar',
                                          dbname='admin'))
    _admin_newdb = client[dbname]
    _admin_newdb.add_user(username, password, roles=roles)
    # we need to get the newdb from the client otherwise
    # newdb has admin rights (!)
    client_mongo_url = MONGO_URL.format(user=username,
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
    # TODO get base url from settings
    mongo_base_url = "mongodb://{username}:{password}@localhost:27019/{dbname}"
    mongo_url = mongo_base_url.format(**settings)
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
