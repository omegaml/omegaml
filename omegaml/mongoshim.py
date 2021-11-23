from urllib.parse import urlencode

from pymongo import MongoClient as RealMongoClient


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
