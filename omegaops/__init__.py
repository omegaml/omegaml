from pymongo.mongo_client import MongoClient

from omegaml.util import urlparse, settings as get_settings

# note no global imports from Django to avoid settings sequence issue

def add_user(user, password, dbname=None):
    """
    add a user to omegaml giving readWrite access rights

    only this user will have access r/w rights to the database.
    """
    from django.contrib.auth.models import User

    dbuser = User.objects.make_random_password(length=36)
    dbname = dbname or User.objects.make_random_password(length=36)
    if isinstance(user, User):
        username = user.username
    else:
        username = user
    add_userdb(dbname, dbuser, password)
    try:
        nb_url = add_usernotebook(username, password)
    except:
        nb_url = 'jupyterhub is not supported'
    config = {
        'default': {
            'dbname': dbname,
            'user': dbuser,
            'password': password,
            'notebook_url': nb_url,
        }
    }
    return config


def add_usernotebook(username, password):
    """
    Add a user on jupyterhub
    """
    from omegaml.util import settings as om_settings
    from omegajobs.hubapi import JupyterHub
    defaults = om_settings()
    hub_user = defaults.OMEGA_JYHUB_USER
    hub_token = defaults.OMEGA_JYHUB_TOKEN
    hub_url = defaults.OMEGA_JYHUB_URL
    hub = JupyterHub(hub_user, hub_token, hub_url)
    hub.create_user(username)
    nb_url = hub.notebook_url(username)
    return nb_url


def add_userdb(dbname, username, password):
    """
    add a new user to the mongo db

    :param dbname: the name of the database
    :param username: the name of the user
    :param password: the password
    :return: (newdb, client_mongo_url) the tuple of the new db instance and
      the mongo_url
    """
    from constance import config

    settings = get_settings()

    roles = [{
        'role': 'readWrite',
        'db': dbname,
    }]
    # create the db but NEVER return this db. it will have admin rights.
    client = MongoClient(settings.MONGO_ADMIN_URL)
    _admin_newdb = client['admin']
    # add user and reset password in case the user was there already
    _admin_newdb.add_user(username, password)
    result = _admin_newdb.command("updateUser", username, pwd=password, roles=roles)
    assert 'ok' in result
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


def authorize_userdb(grant_user, grantee_user, username, password):
    """
    authorize a user to access an existing database

    once granted the grantee_user will be able to access the other user's db
    using the other user's username as the qualifier argument.

    :param dbname:
    :param username:
    :param password:
    :return:
    """
    from django.contrib.auth.models import User

    # get settings from both users
    grant_settings = grant_user.services.get(offering__name='omegaml').settings
    grantee_service = grantee_user.services.get(offering__name='omegaml')
    dbuser = User.objects.make_random_password(length=36)
    dbname = grant_settings.get('default', grant_settings).get('dbname')
    # add user to other db
    add_userdb(dbname, username, password)
    otherdb_config = {
        grant_user.username: {
            'dbname': dbname,
            'user': dbuser,
            'password': password,
        }
    }
    # update grantee's user settings
    grantee_service.settings.update(otherdb_config)
    grantee_service.save()
    return grantee_service.settings


def add_service_deployment(user, config):
    """
    add the service deployment
    """
    from landingpage.models import ServicePlan

    plan = ServicePlan.objects.get(name='omegaml')
    text = 'userid {user.username}<br>apikey {user.api_key.key}'.format(
        **locals())
    user.services.all().delete()
    deployment = user.services.create(user=user,
                                      text=text,
                                      offering=plan,
                                      settings=config)
    return deployment


def complete_service_deployment(deployment, status):
    deployment.status = status
    deployment.save()


def get_client_config(user, qualifier=None, view=False):
    """
    return the full client configuration

    :param view: if True return the internal mongo url, else external as defined in
       constance.MONGO_HOST
    """
    from constance import config

    settings = get_settings()

    qualifier = qualifier or 'default'
    user_settings = user.services.get(offering__name='omegaml').settings
    user_settings = user_settings.get(qualifier, user_settings)
    user_settings['user'] = user_settings.get('username') or user_settings.get('user')

    if not view:
        # provide cluster-external mongo+rabbitmq hosts URL
        mongo_url = settings.BASE_MONGO_URL.format(mongohost=config.MONGO_HOST,
                                                   **user_settings)
        broker_url = config.BROKER_URL
    else:
        # provide cluster-internal mongo+rabbitmq hosts URL
        # parse salient parts of mongourl, e.g.
        # mongodb://user:password@host/dbname
        parsed_url = urlparse.urlparse(settings.OMEGA_MONGO_URL)
        host = parsed_url.netloc
        if '@' in host:
            creds, host = host.split('@', 1)
        mongo_url = settings.BASE_MONGO_URL.format(mongohost=host,
                                                   **user_settings)
        broker_url = settings.OMEGA_BROKER

    # FIXME permission user instead of standard
    client_config = {
        "OMEGA_CELERY_CONFIG": {
            "BROKER_URL": broker_url,
            "CELERY_RESULT_BACKEND": 'amqp',
            "CELERY_ACCEPT_CONTENT": [
                "pickle",
                "json",
            ],
            "CELERY_TASK_SERIALIZER": 'pickle',
        },
        "OMEGA_MONGO_URL": mongo_url,
        "OMEGA_NOTEBOOK_COLLECTION": settings.OMEGA_NOTEBOOK_COLLECTION,
        "OMEGA_TMP": "/tmp",
        "OMEGA_MONGO_COLLECTION": "omegaml",
        "OMEGA_USERID": user.username,
        "OMEGA_APIKEY": user.api_key.key,
    }
    if settings.OMEGA_CELERY_CONFIG['CELERY_ALWAYS_EAGER']:
        client_config['OMEGA_CELERY_CONFIG']['CELERY_ALWAYS_EAGER'] = True
    return client_config


def stop_usernotebook(username):
    """
    Stop a user's notebook

    :param username: the username
    :return:
    """
    from omegaml.util import settings as om_settings
    from omegajobs.hubapi import JupyterHub
    defaults = om_settings()
    hub_user = defaults.OMEGA_JYHUB_USER
    hub_token = defaults.OMEGA_JYHUB_TOKEN
    hub_url = defaults.OMEGA_JYHUB_URL
    hub = JupyterHub(hub_user, hub_token, hub_url)
    hub.stop_notebook(username)


def start_usernotebook(username):
    """
    Start a user's notebook

    :param username: the username
    :return:
    """
    from omegaml.util import settings as om_settings
    from omegajobs.hubapi import JupyterHub
    defaults = om_settings()
    hub_user = defaults.OMEGA_JYHUB_USER
    hub_token = defaults.OMEGA_JYHUB_TOKEN
    hub_url = defaults.OMEGA_JYHUB_URL
    hub = JupyterHub(hub_user, hub_token, hub_url)
    hub.start_notebook(username)
