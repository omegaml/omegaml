from functools import lru_cache
from hashlib import md5
from mongoengine import DoesNotExist

from omegaml.store import OmegaStore


class StreamsProxy(OmegaStore):
    """
    A straight forward adapter to minibatch streams

    Note backends or mixins are disabled for StreamsProxy.

    Usage:
        # insert data to a stream
        om.streams.put(data, 'name')

        # to increase performance, use the stream.append() method
        stream = om.streams.get('name')
        stream.append(data)

        # get a minibatch stream. note it always exists
        om.streams.get('name')

        # get the buffer of a stream
        om.streams.get('name').buffer()

        # get a stream's metadata
        om.streams.metadata('name')

        # get a streaming emitter function
        emitter = om.streams.get('name', lazy=True, **kwargs)
        emitter = om.streams.getl('name', **kwargs)
        # run with a callable
        # -- the callable will be called in parallel
        emitter(lambda window: ...)

        # specify the size (N) or interval (seconds) of the window
        emitter = om.streams.getl('name', size=10, **kwargs)
        emitter = om.streams.getl('name', interval=5, **kwargs)

    See Also:
        minibatch package for details
    """

    # TODO move this implementation to a proper OmegaStore backend or mixin
    # this is a OmegaStore so we can have Metadata support
    # it is called the StreamsProxy because it behaves more like a Mixin
    # rationale for not using a proper Backend on om.datasets is that
    # we wanted the streams.put() method to be really fast, without any lookups
    # It may be worthwhile to reconsider an just make streams.get().append()
    # the high performance alternative
    def __init__(self, prefix=None, bucket=None, defaults=None, mongo_url=None, **kwargs):
        super().__init__(mongo_url=mongo_url, prefix=prefix, bucket=bucket, defaults=defaults)
        cnx_kwargs = self.defaults.OMEGA_MONGO_SSL_KWARGS
        cnx_kwargs.update(kwargs)
        self._stream_kwargs = dict(url=self.mongo_url, **cnx_kwargs)

    def _apply_mixins(self):
        # TODO enable mixins
        # disabled to avoid interference with custom get(), put()
        pass

    def register_backends(self):
        # TODO enable custom backends
        # disabled to avoid interference with custom get(), put()
        pass

    def object_store_key(self, name, *args, **kwargs):
        return f'{self.bucket}.{self.prefix}.{name}.stream'

    def get(self, name, lazy=False, **kwargs):
        import minibatch as mb
        meta = self.metadata(name)
        if meta is None:
            kind_meta = {
                'stream': self.object_store_key(name),
                'kwargs': {
                    'batchsize': kwargs.get('batchsize')
                },
            }
            meta = self.make_metadata(name,
                                      'stream.minibatch',
                                      prefix=self.prefix,
                                      bucket=self.bucket,
                                      kind_meta=kind_meta).save()
        stream_name = meta.kind_meta['stream']
        stream_kwargs = dict(self._stream_kwargs)
        stream_kwargs.update(meta.kind_meta.get('kwargs', {}))
        if not lazy:
            stream = mb.stream(stream_name, **kwargs, **self._stream_kwargs)
        else:
            stream = mb.streaming(stream_name, **kwargs, cnx_kwargs=self._stream_kwargs)
        return stream

    @lru_cache(maxsize=None)
    def _cached_get(self, name, reload=False, _cachex=None):
        if reload:
            # force to avoid cache
            return self.get(name, _cachex=md5().hexdigest())
        return self.get(name)

    def getl(self, name, **kwargs):
        return self.get(name, lazy=True, **kwargs)

    def drop(self, name, force=False):
        meta = self.metadata(name)
        if meta is None and not force:
            raise DoesNotExist()
        stream = self.get(name)
        stream.buffer().delete()
        stream.delete()
        meta.delete() if meta is not None else None
        return True

    def _recreate(self, name):
        self.drop(name)
        return self.get(name)

    def put(self, data, name, append=True):
        (self._cached_get(name) if append else self._recreate()).append(data)
