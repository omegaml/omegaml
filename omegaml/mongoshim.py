from pymongo import MongoClient as RealMongoClient


def MongoClient(*args, **kwargs):
    """
    Shim function adding SSL kwargs on MongoClient instead of changing
    each and every location
    """
    from omegaml import settings
    defaults = settings()
    kwargs.update(defaults.OMEGA_MONGO_SSL_KWARGS)
    return RealMongoClient(*args, **sanitize_mongo_kwargs(kwargs))


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
