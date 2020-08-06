import json

from omegaml.mongoshim import MongoClient
from omegaml.util import urlparse, settings as get_settings, markup, dict_merge


# note no global imports from Django to avoid settings sequence issue


def add_user(user, password, dbname=None, deploy_vhost=False):
    """
    add a user to omegaml giving readWrite access rights

    only this user will have access r/w rights to the database.
    """
    from django.contrib.auth.models import User

    # setup service configuration
    if isinstance(user, User):
        username = user.username
    else:
        username = user
    dbuser = User.objects.make_random_password(length=36)
    dbname = dbname or User.objects.make_random_password(length=36)
    # setup services
    add_userdb(dbname, dbuser, password)
    try:
        nb_url = add_usernotebook(username, password)
    except:
        nb_url = 'jupyterhub is not supported'
    # setup client config
    # see get_client_config for specs on config
    config = {
        'version': 'v3',
        'services': {
            'notebook': {
                'url': nb_url,
            }
        },
        'qualifiers': {
            # TODO simplify -- use a more generic user:password@service/selector format
            'default': {
                'mongodbname': dbname,
                'mongouser': dbuser,
                'mongopassword': password,
            }
        }
    }
    # for local testing we don't deploy vhost since there is no specific worker running
    # TODO find a way to run a local worker for test purpose using per-user vhosts (consider apphub)
    if deploy_vhost:
        brokeruser = dbuser
        brokervhost = dbname or User.objects.make_random_password(length=36)
        add_user_vhost(brokervhost, brokeruser, password)
        config['qualifiers']['default'].update({
            'brokeruser': brokeruser,
            'brokerpassword': password,
            'brokervhost': brokervhost,
        })
    return config
    # else:
    #     # let our own worker serve this user as a courtesy
    #     import omegaml as om
    #     account_default_queue = '{}-default'.format(user.username)
    #     om.runtime.celeryapp.control.add_consumer(account_default_queue, reply=True)
    # return config


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
    client_mongo_url = settings.BASE_MONGO_URL.format(mongouser=username,
                                                      mongohost=mongohost,
                                                      mongopassword=password,
                                                      mongodbname=dbname)
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
    dbname = grant_settings['qualifiers'].get('default', grant_settings).get('mongodbname')
    # add user to other db
    add_userdb(dbname, username, password)
    otherdb_config = {
        grant_user.username: {
            'mongodbname': dbname,
            'mongouser': dbuser,
            'mongopassword': password,
        }
    }
    # update grantee's user settings
    dict_merge(grantee_service.settings, otherdb_config)
    grantee_service.save()
    return grantee_service.settings


def add_user_vhost(vhost_name, vhost_username, vhost_password):
    import pyrabbit2 as rmq
    defaults = get_settings()
    parsed = urlparse.urlparse(defaults.OMEGA_BROKERAPI_URL)
    host = '{}:{}'.format(parsed.hostname, parsed.port)
    username = parsed.username
    password = parsed.password
    client = rmq.Client(host, username, password)
    client.create_vhost(vhost_name)
    client.create_user(vhost_username, vhost_password)
    client.set_vhost_permissions(vhost_name, vhost_username, '.*', '.*', '.*')


def authorize_user_vhost(grant_user, grantee_user, username, password):
    import pyrabbit2 as rmq
    # get settings from both users
    grant_settings = grant_user.services.get(offering__name='omegaml').settings
    grantee_service = grantee_user.services.get(offering__name='omegaml')
    # build admin broker url
    settings = get_settings()
    parsed = urlparse.urlparse(settings.OMEGA_BROKERAPI_URL)
    host = '{}:{}'.format(parsed.hostname, parsed.port)
    client = rmq.Client(host, parsed.username, parsed.password)
    # add user to other db
    vhost_name = grant_settings['qualifiers'].get('default', grant_settings).get('brokervhost')
    client.set_vhost_permissions(vhost_name, username, '.*', '.*', '.*')
    otherdb_config = {
        grant_user.username: {
            'brokervhost': vhost_name,
            'brokeruser': username,
            'brokerpassword': password,
        }
    }
    # update grantee's user settings
    dict_merge(grantee_service.settings, otherdb_config)
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

    Args:
        view (bool): if True return the internal mongo url, else external as defined in
       constance.MONGO_HOST

    Notes:
        The client configuration is in user.services.settings for offering='omegaml'
        provided by landingpage/paasdeploy. settings is a dict (JSON formatted on
        input) of the following format

        v2:
            "version": "v2",
            'services' : {
               'jupyter': {
                  'image': 'imagename:tag',
                  'node_selector': 'key=value',
                  'namespace': 'namespace',
                  'affinity_role': 'worker',
               },
               'notebook': {
                  'url': 'http...',
               },
               'runtime': {
                   'image': 'imagename:tag',
                   'node_selector': 'key=value',
                   'namespace': 'namespace',
                   'affinity_role': 'worker',
               },
            },
            'qualifiers': {
                <qualifier>: {
                    # mandatory
                    "mongodbname": "<mongo dbname>",
                    "mongouser": "<mongo user>",
                    "mongopassword": "<mongo password",
                    # optional, if not provided defaults to environment
                    "mongohost": "<mongo host:port>", # external
                    "mongohost.in": "<mongo host:port>", # internal
                },
                [...]
            },

        v1:
            <qualifier>: {
                "dbname": "<mongo dbname>",
                "user": "<mongo user>",
                "password": "<mongo password",
                "brokerhost": "<broker url:port", # external
                "brokerhost.in": "<broker url:port", # internal
            },
            [...]

        v0:
            "dbname": "<mongo dbname>",
            "username": "<mongo user>",
            "password": "<mongo password",
    """
    from constance import config
    # -- get settings from environment
    #    there are several sources:
    #      settings = from defaults
    #      user.services.settings = from deployed instance
    settings = get_settings()
    qualifier = qualifier or 'default'
    user_settings = user.services.get(offering__name='omegaml').settings
    # -- parse user settings to most recent version
    #    we support multiple config versions for legacy reasons
    #    every parser must return to the most recent version spec as per above
    PARSERS = {
        'v1': parse_client_config_v1,
        'v2': parse_client_config_v2,
        'v3': parse_client_config_v3,
    }
    user_settings_version = user_settings.get('version', 'v1')
    parser = PARSERS[user_settings_version]
    user_settings = parser(user_settings, qualifier, settings, config)
    qualifier_settings = user_settings['qualifiers'][qualifier]
    # -- prepare actual client config based on user settings
    if view:
        mongohost_key = 'mongohost.in'
        brokerhost_key = 'brokerhost.in'
    else:
        mongohost_key = 'mongohost'
        brokerhost_key = 'brokerhost'
    mongo_url = settings.BASE_MONGO_URL.format(mongouser=qualifier_settings['mongouser'],
                                               mongopassword=qualifier_settings['mongopassword'],
                                               mongohost=qualifier_settings[mongohost_key],
                                               mongodbname=qualifier_settings['mongodbname'])
    broker_url = settings.BASE_BROKER_URL.format(brokeruser=qualifier_settings['brokeruser'],
                                                 brokerpassword=qualifier_settings['brokerpassword'],
                                                 brokerhost=qualifier_settings[brokerhost_key],
                                                 brokervhost=qualifier_settings['brokervhost'])
    broker_url = broker_url.replace('None:None@', '')
    default_queue = qualifier_settings.get('routing') or user_settings.get('routing') or 'default'
    omega_defaults = user_settings['services']['omegaml']['defaults']
    # FIXME permission user instead of standard
    client_config = {
        "OMEGA_CELERY_CONFIG": {
            "BROKER_URL": broker_url,
            "CELERY_RESULT_BACKEND": 'amqp',
            "CELERY_ACCEPT_CONTENT": [
                "pickle",
                "json",
            ],
            "CELERY_DEFAULT_QUEUE": default_queue,
            "CELERY_TASK_SERIALIZER": 'pickle',
            "BROKER_USE_SSL": settings.OMEGA_USESSL,
        },
        "OMEGA_MONGO_URL": mongo_url,
        "OMEGA_NOTEBOOK_COLLECTION": settings.OMEGA_NOTEBOOK_COLLECTION,
        "OMEGA_TMP": "/tmp",
        "OMEGA_MONGO_COLLECTION": "omegaml",
        "OMEGA_USERID": user.username,
        "OMEGA_APIKEY": user.api_key.key,
    }
    # allow any updates to effectively omegaml.defaults
    dict_merge(client_config, omega_defaults)

    if view:
        # only include internals if needed
        client_config.update({
            "JUPYTER_IMAGE": user_settings['services']['jupyter']['image'],
            "JUPYTER_NODE_SELECTOR": user_settings['services']['jupyter']['node_selector'],
            "JUPYTER_NAMESPACE": user_settings['services']['jupyter']['namespace'],
            "JUPYTER_AFFINITY_ROLE": user_settings['services']['jupyter']['affinity_role'],
            "RUNTIME_WORKER_IMAGE": user_settings['services']['runtime']['image'],
            "RUNTIME_NODE_SELECTOR": user_settings['services']['runtime']['node_selector'],
            "RUNTIME_NAMESPACE": user_settings['services']['runtime']['namespace'],
            "RUNTIME_AFFINITY_ROLE": user_settings['services']['runtime']['affinity_role'],
            "CLUSTER_STORAGE": user_settings['services']['cluster']['storage'],
            "JUPYTER_CONFIG": user_settings['services']['jupyter']['config'],
        })

    if settings.OMEGA_CELERY_CONFIG['CELERY_ALWAYS_EAGER']:
        client_config['OMEGA_CELERY_CONFIG']['CELERY_ALWAYS_EAGER'] = True

    # recursively replace place holders
    # {username} - user's name
    def expand_placeholders(d):
        for k, v in d.items():
            if isinstance(v, dict):
                expand_placeholders(v)
            elif isinstance(v, str):
                d[k] = v.format(username=user.username)
            else:
                pass

    expand_placeholders(client_config)
    return client_config


def parse_client_config_v1(user_settings, qualifier, settings, config):
    # parse config v0, v1 to current format
    # -- mongo credentials
    user_settings = user_settings.get(qualifier, user_settings)
    mongouser = user_settings.get('username') or user_settings.get('user')
    mongopassword = user_settings.get('password')
    mongodbname = user_settings.get('dbname')
    # -- external hosts
    mongohost_ext = config.MONGO_HOST
    broker_host_ext = config.BROKER_HOST
    # -- internal hosts
    # -- mongo
    parsed_url = urlparse.urlparse(settings.OMEGA_MONGO_URL)
    host = parsed_url.netloc
    if '@' in host:
        creds, host = host.split('@', 1)
    mongohost_in = host
    # -- broker
    parsed_url = urlparse.urlparse(settings.OMEGA_BROKER)
    host = parsed_url.netloc
    if '@' in host:
        creds, host = host.split('@', 1)
    broker_host_in = host
    broker_defaults = urlparse.urlparse(settings.OMEGA_BROKER)
    # prepare parsed
    parsed = {
        'services': {
            'jupyter': {
                'image': config.JUPYTER_IMAGE,
                'node_selector': config.JUPYTER_NODE_SELECTOR,
                'namespace': config.JUPYTER_NAMESPACE,
                'affinity_role': config.JUPYTER_AFFINITY_ROLE,
                'config': markup(config.JUPYTER_CONFIG or '{}'),
            },
            'runtime': {
                'image': config.RUNTIME_IMAGE,
                'node_selector': config.RUNTIME_NODE_SELECTOR,
                'namespace': config.RUNTIME_NAMESPACE,
                'affinity_role': config.RUNTIME_AFFINITY_ROLE,
            },
            'omegaml': {
                'defaults': markup(config.OMEGA_DEFAULTS or '{}'),
            },
            'cluster': {
                'storage': None,
                # specify as dict of lists
                # {
                #   'volumes': [
                #      dict(name='pylib', persistentVolumeClaim='worker-{username}')
                #   ],
                #   'volumeMounts': [
                #      dict(name='pylib', mountPath='/path/in/pod')
                #   ]
                # }
            }
        },
        'qualifiers': {
            qualifier: {
                'mongohost': mongohost_ext,
                'mongohost.in': mongohost_in,
                'mongouser': mongouser,
                'mongopassword': mongopassword,
                'mongodbname': mongodbname,
                'brokerhost': broker_host_ext,
                'brokerhost.in': broker_host_in,
                'brokeruser': broker_defaults.username,
                'brokerpassword': broker_defaults.password,
                'brokervhost': sanitize_vhost(broker_defaults.path),
            }
        }
    }
    return parsed


def parse_client_config_v2(user_settings, qualifier, settings, config):
    # parse config v2 to current format
    qualifiers = dict(user_settings.get('qualifiers'))
    qualifier_settings = qualifiers.get(qualifier, qualifiers['default'])
    # -- external hosts
    mongohost_ext = qualifier_settings.get('mongohost') or config.MONGO_HOST
    broker_url_ext = qualifier_settings.get('brokerurl') or config.BROKER_URL
    # -- internal hosts
    parsed_url = urlparse.urlparse(settings.OMEGA_MONGO_URL)
    host = parsed_url.netloc
    if '@' in host:
        creds, host = host.split('@', 1)
    mongohost_in = qualifier_settings.get('mongohost.in') or host
    broker_url_in = qualifier_settings.get('brokerurl.in') or settings.OMEGA_BROKER
    parsed_url = urlparse.urlparse(settings.OMEGA_BROKER)
    host = parsed_url.netloc
    if '@' in host:
        creds, host = host.split('@', 1)
    broker_host_in = qualifier_settings.get('brokerhost.in') or host
    parsed_url = urlparse.urlparse(config.BROKER_URL)
    host = parsed_url.netloc
    if '@' in host:
        creds, host = host.split('@', 1)
    broker_host_ext = qualifier_settings.get('brokerhost') or host
    broker_defaults = urlparse.urlparse(broker_url_in)
    # note we specify parsers for clarity, values can be overriden below
    parsed = {
        'services': {
            'jupyter': {
                'image': config.JUPYTER_IMAGE,
                'node_selector': config.JUPYTER_NODE_SELECTOR,
                'namespace': config.JUPYTER_NAMESPACE,
                'affinity_role': config.JUPYTER_AFFINITY_ROLE,
                'config': markup(config.JUPYTER_CONFIG or '{}'),
            },
            'runtime': {
                'brokerurl': broker_url_ext,
                'brokerurl.in': broker_url_in,
                'image': config.RUNTIME_IMAGE,
                'node_selector': config.RUNTIME_NODE_SELECTOR,
                'namespace': config.RUNTIME_NAMESPACE,
                'affinity_role': config.RUNTIME_AFFINITY_ROLE,
            },
            'omegaml': {
                'defaults': json.loads(config.OMEGA_DEFAULTS or '{}'),
            },
            'cluster': {
                'storage': None,
            }},
        'qualifiers': {
            qualifier: {
                'mongohost': mongohost_ext,
                'mongohost.in': mongohost_in,
                'mongouser': qualifier_settings.get('mongouser'),
                'mongopassword': qualifier_settings.get('mongopassword'),
                'mongodbname': qualifier_settings.get('mongodbname'),
                'brokerhost': broker_host_ext,
                'brokerhost.in': broker_host_in,
                'brokeruser': qualifier_settings.get('brokeruser', broker_defaults.username),
                'brokerpassword': qualifier_settings.get('brokerpassword', broker_defaults.password),
                'brokervhost': qualifier_settings.get('brokervhost', sanitize_vhost(broker_defaults.path)),
            }
        },
    }
    # the user provided values take precedence, if any
    parsed['services']['jupyter'].update(user_settings['services'].get('jupyter', {}))
    parsed['services']['runtime'].update(user_settings['services'].get('runtime', {}))
    parsed['qualifiers'][qualifier].update(qualifier_settings)
    return parsed


def parse_client_config_v3(user_settings, qualifier, settings, config):
    # parse config v2 to current format
    qualifiers = dict(user_settings.get('qualifiers'))
    qualifier_settings = qualifiers.get(qualifier, qualifiers['default'])
    # -- external hosts
    mongohost_ext = qualifier_settings.get('mongohost') or config.MONGO_HOST
    broker_host_ext = qualifier_settings.get('brokerhost') or config.BROKER_HOST
    # -- internal hosts
    parsed_url = urlparse.urlparse(settings.OMEGA_MONGO_URL)
    host = parsed_url.netloc
    if '@' in host:
        creds, host = host.split('@', 1)
    mongohost_in = qualifier_settings.get('mongohost.in') or host
    # FIXME this is a hack to support an old-style default broker. Must simplify, resolve duplicate OMEGA_BROKER/BROKER_HOST
    broker_defaults = urlparse.urlparse(config.BROKER_URL)
    broker_host_in = qualifier_settings.get('brokerhost.in') or settings.OMEGA_BROKER_HOST
    # note we specify parsers for clarity, values can be overriden below
    parsed = {
        'services': {
            'jupyter': {
                'image': config.JUPYTER_IMAGE,
                'node_selector': config.JUPYTER_NODE_SELECTOR,
                'namespace': config.JUPYTER_NAMESPACE,
                'affinity_role': config.JUPYTER_AFFINITY_ROLE,
                'config': json.loads(config.JUPYTER_CONFIG or '{}'),
            },
            'runtime': {
                'image': config.RUNTIME_IMAGE,
                'node_selector': config.RUNTIME_NODE_SELECTOR,
                'namespace': config.RUNTIME_NAMESPACE,
                'affinity_role': config.RUNTIME_AFFINITY_ROLE,
            },
            'omegaml': {
                'defaults': json.loads(config.OMEGA_DEFAULTS or '{}'),
            },
            'cluster': {
                'storage': json.loads(config.CLUSTER_STORAGE or '{}'),
                # specify as dict of lists
                # {
                #   'volumes': [
                #      dict(name='pylib',
                #           persistent_volume_claim':
                #               dict(claimName='worker-{username}',
                #               readOnly=False))
                #   ],
                #   'volumeMounts': [
                #      dict(name='pylib', mountPath='/path/in/pod')
                #   ]
                # }
            }
        },
        'qualifiers': {
            qualifier: {
                'mongohost': mongohost_ext,
                'mongohost.in': mongohost_in,
                'mongouser': qualifier_settings.get('mongouser'),
                'mongopassword': qualifier_settings.get('mongopassword'),
                'mongodbname': qualifier_settings.get('mongodbname'),
                'brokerhost': broker_host_ext,
                'brokerhost.in': broker_host_in,
                'brokeruser': qualifier_settings.get('brokeruser', broker_defaults.username),
                'brokerpassword': qualifier_settings.get('brokerpassword', broker_defaults.password),
                'brokervhost': qualifier_settings.get('brokervhost', sanitize_vhost(broker_defaults.path)),
            }
        },
    }
    # the user provided values take precedence, if any
    dict_merge(parsed['services']['jupyter'], user_settings['services'].get('jupyter', {}))
    dict_merge(parsed['services']['runtime'], user_settings['services'].get('runtime', {}))
    dict_merge(parsed['services']['omegaml'], user_settings['services'].get('omegaml', {}))
    dict_merge(parsed['services']['cluster'], user_settings['services'].get('cluster', {}))
    dict_merge(parsed['qualifiers'][qualifier], qualifier_settings)
    return parsed


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


def sanitize_vhost(vhost):
    if vhost.startswith('/'):
        return vhost[1:]
    return vhost.replace('//', '/')
