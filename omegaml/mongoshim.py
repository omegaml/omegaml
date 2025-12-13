import atexit
import logging
import warnings
from time import sleep
from urllib.parse import urlencode

from pymongo import MongoClient as RealMongoClient
from pymongo.errors import AutoReconnect, ConnectionFailure

from omegaml.util import find_instances, ProcessLocal


def MongoClient(*args, **kwargs):
    """
    Shim function adding SSL kwargs on MongoClient instead of changing
    each and every location
    """
    from omegaml import settings
    defaults = settings()
    mongo_kwargs = dict(defaults.OMEGA_MONGO_SSL_KWARGS)
    mongo_kwargs.update(kwargs)
    client = RealMongoClient(*args, **sanitize_mongo_kwargs(mongo_kwargs))
    return client


def patch_mongoengine():
    # this is to avoid mongoengine's MongoClient instances in subprocesses
    # resulting in "MongoClient opened before fork" warning
    # the source of the problem is that mongoengine stores MongoClients in
    # a module-global dictionary. here we replace these module-globals with
    # process-global dictionaries, ProcessLocal
    from mongoengine import connection
    # There is a fix in mongoengine 18.0 that is supposed to introduce the same
    # behavior using disconnection_all(), however in some cases this is the
    # actual source of the warning due to calling connection.close()
    # see https://github.com/MongoEngine/mongoengine/pull/2038
    # -- the implemented solution simply ensures MongoClients get recreated
    #    whenever needed
    if not isinstance(connection._connection_settings, ProcessLocal):
        setattr(connection, '_connection_settings', ProcessLocal(connection._connection_settings))
        setattr(connection, '_connections', ProcessLocal(connection._connections))
        setattr(connection, '_dbs', ProcessLocal(connection._dbs))
    return


def close_all_clients():
    from mongoengine import disconnect_all
    # close mongoengine clients
    try:
        disconnect_all()
    except:
        # ignore any errors
        pass
    # close remaining MongoClients
    clients = find_instances(RealMongoClient)
    for client in clients:
        try:
            client.close()
        except Exception:
            # ignore any errors
            pass


def sanitize_mongo_kwargs(kwargs):
    # keep kwargs sane
    # -- if we receive "use_ssl" = False from cloud config but have
    #    a local CA defined, remove it. Otherwise mongo raises ConfigurationError
    kwargs = dict(kwargs)
    if 'ssl' in kwargs:
        # ssl is alias to tls, should override tls (assume ssl is user-specified)
        # see https://pymongo.readthedocs.io/en/stable/api/pymongo/mongo_client.html
        kwargs['tls'] = kwargs['ssl']
        del kwargs['ssl']
    if 'tlsCAFile' in kwargs and not kwargs.get('tls'):
        del kwargs['tlsCAFile']
    if 'ssl_ca_certs' in kwargs and not kwargs.get('tls'):
        del kwargs['ssl_ca_certs']
    logger = logging.getLogger('pymongo.serverSelection')
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug('MongoDB connection kwargs: %s', kwargs)
    else:
        # silence pymongo debug logging for server selection
        # -- since pymongo 4.7 pymongo logs server selection at INFO level
        # -- this is too verbose for normal operation
        # -- will be fixed in pymongo 4.7.3
        # -- https://jira.mongodb.org/browse/PYTHON-4261
        logger.setLevel(logging.ERROR)
    return kwargs


def mongo_url(om, drop_kwargs=None):
    url_kwargs = sanitize_mongo_kwargs(om.defaults.OMEGA_MONGO_SSL_KWARGS)
    if drop_kwargs:
        for kw in drop_kwargs:
            url_kwargs.pop(kw, None)
    url_kwargs = urlencode(url_kwargs)
    url_kwargs = url_kwargs.replace('True', 'true').replace('False', 'false')
    mongo_url = (om.datasets.mongo_url + '?authSource=admin&' + url_kwargs)
    return mongo_url


def waitForConnection(client):
    _exc = None
    # adopted from https://pymongo.readthedocs.io/en/4.10.1/api/pymongo/mongo_client.html#pymongo.mongo_client.MongoClient.server_info
    for i in range(10):
        try:
            # The ping command is cheap and does not require auth.
            import pymongo
            client.admin.command('ping')
        except (ConnectionFailure, AutoReconnect, AssertionError) as e:
            warnings.warn('Connection to MongoDB failed. Retrying in 0.01s')
            sleep(0.01)
            _exc = e
        else:
            _exc = None
            break
    if _exc is not None:
        raise _exc


# -- patch mongoengine's global connection dictionaries to be ProcessLocal()s
patch_mongoengine()
# -- register closing all mongo clients at exit
atexit.register(close_all_clients)
# -- filter pymongo's resourcewarnings, as we close all clients at exit
warnings.filterwarnings('ignore', category=ResourceWarning, module='omegaml|minibatch')
