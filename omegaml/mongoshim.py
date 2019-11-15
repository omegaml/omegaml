from pymongo import MongoClient as RealMongoClient


def MongoClient(*args, **kwargs):
    """
    Shim function adding SSL kwargs on MongoClient instead of changing 
    each and every location
    """
    from omegaml import settings
    defaults = settings()
    kwargs.update(defaults.OMEGA_MONGO_SSL_KWARGS)
    return RealMongoClient(*args, **kwargs)