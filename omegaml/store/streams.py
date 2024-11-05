import warnings
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
        self._stream_cnx_kwargs = dict(url=self.mongo_url, **cnx_kwargs)

    def _mixins_conditional(self, cls, obj):
        # only allow mixins that do not interfere with streams get/put
        return cls.supports(obj, prefix='streams/') if hasattr(cls, 'supports') else False

    def register_backends(self):
        # TODO enable custom backends
        # disabled to avoid interference with custom get(), put()
        pass

    def _qualified_stream(self, name, *args, **kwargs):
        return f'{self.bucket}.{self.prefix}.{name}.stream'

    def get(self, name, lazy=False, source=None, source_kwargs=None, autoattach=True,
            streaming=None, **kwargs):
        """
        get or create a new minibatch stream

        Retrieves a minibatch stream that is scoped to the current
        bucket. The stream is initially not attached to any source.

        To attach a source, pass one of the following:
            * 'runtime' - attaches to receive om.runtime events
            * '<dataset>' - attaches to the given dataset in om.datasets,
              receiving insert events
            * source - a valid minibatch source instance

        To attach to a source in a specific omega instance, pass
        the tuple (om, <source>). To pass additional kwargs to the source,
        pass (om, <source>, kwargs).

        Args:
            name (str): name of the stream
            lazy (bool): if True returns a streaming function, else
              the stream itself (default).
            source (str|Omega): if 'runtime' or an Omega instance,
              attaches to the runtime broker
            streaming (dict): kwargs passed to stream.streaming() in case
              of lazy=True, stored in the stream metadata in case this is
              a new stream
            autoattach (bool): if True, automatically attach to the source,
              if any. Defaults to True
            **kwargs: kwargs passed to minibatch.stream() if this is a new
                stream

        Returns:
            either of the following, depending on lazy:
            * stream (minibatch.Stream) : the stream object
            * streaming (callable) : the streaming function
        """
        # ensure we have an existing stream
        streaming = streaming or {}
        source_kwargs = source_kwargs or {}
        if isinstance(source, (tuple, list)):
            om, source, source_kwargs, *_ = list(source) + [{}]
        meta = self.metadata(name)
        if meta is None:
            meta = self._create_stream(name, source, kwargs, source_kwargs, streaming)
        # recreate the stream (buffer) or streaming (callable) object
        stream = self._get_actual_stream(meta, source=source,
                                         source_kwargs=source_kwargs,
                                         autoattach=autoattach,
                                         **kwargs)
        if lazy:
            streaming_kwargs = meta.kind_meta['stream']['streaming_kwargs']
            streaming_kwargs.update(streaming)
            stream = stream.streaming(**streaming_kwargs)
        return stream

    def _create_stream(self, name, source, stream_kwargs, source_kwargs, streaming_kwargs):
        scalar_types = (int, float, str, bool, dict)
        kind_meta = {
            'stream': {
                'name': self._qualified_stream(name),
                'stream_kwargs': stream_kwargs,
                'streaming_kwargs': {
                    # remove any window function passed in
                    k: v for k, v in streaming_kwargs.items() if isinstance(v, scalar_types)
                }
            },
            'attach': {
                'source': source if isinstance(source, str) else None,
                'source_kwargs': source_kwargs or {},
            }
        }
        meta = self.make_metadata(name,
                                  'stream.minibatch',
                                  prefix=self.prefix,
                                  bucket=self.bucket,
                                  kind_meta=kind_meta).save()
        return meta

    def _get_actual_stream(self, meta, source=None, source_kwargs=None,
                           autoattach=True, **kwargs):
        import minibatch as mb
        import omegaml as om
        # apply stream_kwargs
        stream_meta = dict(meta.kind_meta.get('stream', {}))
        stream_name = stream_meta.get('name')
        stream_kwargs = dict(self._stream_cnx_kwargs)
        stream_kwargs.update(stream_meta.get('stream_kwargs', {}))
        stream_kwargs.update(kwargs)
        stream = mb.stream(stream_name, **stream_kwargs)
        source_meta = meta.kind_meta.get('attach', {})
        source = source or source_meta.get('source')
        if source and autoattach:
            # apply source_kwargs
            _source_kwargs = dict(source_meta.get('source_kwargs', {}))
            _source_kwargs.update(source_kwargs)
            self._autoattach(om, stream, source, _source_kwargs) if autoattach else None
        return stream

    def _autoattach(self, om, stream, source, source_kwargs):
        if source == 'runtime':
            from minibatch.contrib.celery import CeleryEventSource
            stream.attach(CeleryEventSource(om.runtime.celeryapp, **source_kwargs))
        elif isinstance(source, str):
            # a dataset name was given
            om = om[self.bucket] if isinstance(om, om.Omega) else om.setup()[self.bucket]
            if om.datasets.metadata(source) is not None:
                from minibatch.contrib.omegaml import DatasetSource
                stream.attach(DatasetSource(om, source, **source_kwargs))
            else:
                raise ValueError(f'cannot attach non-existing dataset {source} to {stream}')
        elif hasattr(source, 'stream'):
            stream.attach(source)
        elif source is not None:
            raise ValueError(f'cannot attach {source} to {stream}')

    def _cached_get(self, name, reload=False, _cachex=None):
        # SEC: CWE-916
        # - status: wontfix
        # - reason: hashcode is used purely for name resolution, not a security function
        if reload:
            # force to avoid cache
            return self.get(name, _cachex=md5().hexdigest())
        return self.get(name)

    def getl(self, name, **kwargs):
        return self.get(name, lazy=True, streaming=kwargs)

    def drop(self, name, force=False, keep_data=True, **kwargs):
        meta = self.metadata(name)
        if meta is None and not force:
            from mongoengine import DoesNotExist
            raise DoesNotExist()
        if keep_data is False:
            try:
                stream = self.get(name, autoattach=False)
                stream.clear()
                stream.stop()
                stream.delete()
            except Exception as e:
                warnings.warn(f'could not delete stream data {name} due to {e}')
        meta.delete() if meta is not None else None
        return True

    def _recreate(self, name):
        self.drop(name)
        return self.get(name)

    def put(self, data, name, append=True, **kwargs):
        (self._cached_get(name) if append else self._recreate(name)).append(data)
