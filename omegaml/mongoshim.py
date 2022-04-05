from pymongo import MongoClient as RealMongoClient
from pymongo.errors import AutoReconnect, ConnectionFailure
from time import sleep
from urllib.parse import urlencode


def MongoClient(*args, **kwargs):
    """
    Shim function adding SSL kwargs on MongoClient instead of changing
    each and every location
    """
    from omegaml import settings
    defaults = settings()
    mongo_kwargs = dict(defaults.OMEGA_MONGO_SSL_KWARGS)
    mongo_kwargs.update(kwargs)
    return RealMongoClient(*args, **sanitize_mongo_kwargs(mongo_kwargs))


def sanitize_mongo_kwargs(kwargs):
    # keep kwargs sane
    # -- if we receive "use_ssl" = False from cloud config but have
    #    a local CA defined, remove it. Otherwise mongo raises ConfigurationError
    kwargs = dict(kwargs)
    if 'tlsCAFile' in kwargs and not kwargs.get('ssl'):
        del kwargs['tlsCAFile']
    if 'ssl_ca_certs' in kwargs and not kwargs.get('ssl'):
        del kwargs['ssl_ca_certs']
    return kwargs


def mongo_url(om):
    mongo_url = (om.datasets.mongo_url + '?authSource=admin&' +
                 urlencode(sanitize_mongo_kwargs(om.defaults.OMEGA_MONGO_SSL_KWARGS)))
    return mongo_url


def waitForConnection(client):
    _exc = None
    command = client.admin.command
    for i in range(100):
        try:
            # The ping command is cheap and does not require auth.
            command('ping')
        except (ConnectionFailure, AutoReconnect) as e:
            sleep(0.01)
            _exc = e
        else:
            _exc = None
            break
    if _exc is not None:
        raise _exc


