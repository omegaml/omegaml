import functools
import json
import logging
import os
import time
from collections.abc import Callable
from datetime import datetime
from hashlib import pbkdf2_hmac
from random import random
from typing import Any
from uuid import uuid4

from jose import jwe
from minibatch.tests.util import LocalExecutor

from omegaml.util import tryOr, utcnow

logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')


class StreamableResourceMixin:
    """resource mixin to handle streaming results in line of by handing-off to a streaming server

    Depending on om.defaults.OMEGA_EVENTS_STREAMER:

    * 'inline' => will respond with server-sent events (SSE) stream
    * 'ssechat' => will respond with a redirect to a event server which then serves the event stream

    Rationale:
        * inline is a blocking generator, that is it will occupy a wsgi process until done, thus
          limiting capacity
        * ssechat redirects to a threaded event server, which then processes the event stream;
          because ssechat is threaded it can handle many more concurrent requests

    Alternatives:
        * for higher scalability, consider pushpin, a GRIP proxy that handles streams concurrently;
          in this case needs an additional STREAMER implementation that responds with GRIP headers

    See Also:
        * https://pushpin.org/ for a GRIP proxy
        * ssechat.py for our implementation that does not have additional dependencies

    Testing:
        * use honcho start to run all required servers from the Procfile
    """

    SECRET_KEY = os.getenv('SECRET_KEY', 'ec3d75c6f5b3965f24f148969b1c82d57246a8aab46393b55ba18d712fa1a0ad')
    PBKDF_ITER = int(os.getenv('PBKDF_ITER', '500000'))

    def __init__(self, *args, streamer=None, **kwargs):
        self.streamer = streamer  # enable testing inline or ssechat

    def prepare_streaming_result(self, promise=None, resource_name=None, raw=False, stream=None):
        """prepare result for event streaming

        Args:
            promise (celery.AsyncResult): a celery result to be resolved
            resource_name (str): the name of the resource being served
            stream (str): optional, defaults to promise.id, precedes promise.id if specified
            streamer (str): the streamer name, 'inline' for inline streaming (blocking), or
                'ssechat' for handing off to async ssechat server

        Returns:
            str | tuple: a serializable result (str) or a Flask-compatible tuple of (body, status_code, location, cookies)
        """
        stream = stream or promise.id  # type: str
        # functions that handle streaming
        #    name => method(stream)
        STREAMERS = {
            'inline': self._inline_streaming,
            'ssechat': self._handoff_to_ssechat,
        }  # type: Dict[str, Callable[..., Any]]
        _default_streamer = STREAMERS.get('inline')
        streaming_method = STREAMERS.get(self.streamer, _default_streamer)
        return streaming_method(stream, resource_name=resource_name, raw=raw)

    def prepare_result(self, chunk, **kwargs):
        return dict(chunk)

    def _inline_streaming(self, stream, raw=None, resource_name=None):
        # implement event streaming as a blocking inline generator
        class Sink(list):
            def put(self, chunks):
                self.extend(chunks)

            def __bool__(self):
                return True  # required to make work with minibatch

        om = self.om
        buffer = Sink()
        logger.debug("stream_result: getting stream")
        stream_name = f'.system/complete/{stream}'
        streaming = om.streams.getl(
            stream_name,
            executor=LocalExecutor(),
            sink=buffer,
            size=om.defaults.OMEGA_EVENTS_BATCHSIZE,  # limit messages in each steps (reduces memory allocation)
            interval=1,
            emitter=FlushWindow,
        )
        # -- emitter to buffer as a sink
        emitter = streaming.make(lambda window: window.data)

        @exponential_backoff(
            initial_interval=0.0001,  # sleep in seconds
            max_interval=1.0,  # max time to wait in seconds
            timeout=om.defaults.OMEGA_EVENTS_TIMEOUT,  # timeout in seconds, max
            factor=2.0,  # exponential growth for interval
            jitter=True,  # add some jitter to distribute load randomly
        )
        def stream_result(resource_name: str, emitter, buffer, raw: bool = False):
            # process stream, one message at a time
            logger.debug("stream_result: attempting to get new events")
            logger.debug(f"stream contents {emitter.stream.buffer()}")
            emitter.run(blocking=False)  # this emits new data to the Sink() buffer
            for chunk in buffer:
                logger.debug(f"stream_result: received chunk {chunk}")
                finish_reason = chunk.get('stream_complete', '')
                message = chunk.get('message')
                should_stop = finish_reason.startswith('stop')
                has_error = finish_reason.startswith('error')
                data = self.prepare_result(chunk, resource_name=resource_name) if not should_stop else None
                data.update(data.pop('result', {})) if raw and isinstance(data, dict) else data
                yield data, should_stop
                if has_error:
                    raise RuntimeError(message or finish_reason)
            buffer.clear()

        try:
            yield from stream_result(resource_name, emitter, buffer, raw=raw)
        finally:
            emitter.stream.clear()
            om.streams.drop(stream_name, force=True)
            logger.debug("done:stream_result closing response")

    def _handoff_to_ssechat(self, stream, raw=False, resource_name=None):
        # implement sse event streaming by 302 redirect, handing off to streaming endpoint
        def encrypt_payload(payload):
            session_id = uuid4().hex
            # SEC: A256CGM is the recommended algorithm for JWE, https://datatracker.ietf.org/doc/html/rfc7518#section-5.1
            #      implementation of JWE by the python-jose package
            key = pbkdf2_hmac(
                'sha256', self.SECRET_KEY.encode('utf-8'), str(session_id).encode('utf-8'), self.PBKDF_ITER
            )
            token = jwe.encrypt(json.dumps(payload), key, algorithm='dir', encryption='A256GCM')
            logger.debug(f'key {key}')
            logger.debug(f'token {token}')
            return session_id, token.decode('utf-8')

        def make_secure_cookies(payload):
            session_id, token = encrypt_payload(payload)
            cookies = {
                'session_id': session_id,
                'token': token,
            }
            return cookies

        payload = {
            'stream': str(stream),
            'userid': tryOr(lambda: self.om.runtime.auth.userid, None),
            'qualifier': tryOr(lambda: self.om.runtime.auth.qualifier, None),
            'created': utcnow().isoformat(),
        }
        cookies = make_secure_cookies(payload)
        location = self.om.defaults.OMEGA_EVENTS_STREAMER_URL
        # redirect client, preserving the headers and http method
        # -- rfc9110 on 302/307: a user agent MAY change the request method from POST to GET
        #    for the subsequent request. If this behavior is undesired, the 307 (Temporary Redirect)
        #    status code can be used instead.
        # -- https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/307
        # -- https://www.rfc-editor.org/rfc/rfc9110#status.307
        return '', 307, {'Location': location, 'Content-Type': 'text/event-stream'}, cookies


def exponential_backoff(
    initial_interval: float = 0.0001,
    max_interval: float = 1.0,
    timeout: float = 10.0,
    factor: float = 2.0,
    jitter: bool = True,
):
    """
    A general-purpose decorator that applies exponential backoff with timeout to
    any polling/streaming function (generator or callable).

    It does NOT inspect yielded values, check for keys like 'stream_complete', or
    assume anything about the function's internal logic.

    The wrapped function is responsible for its own termination condition.
    This decorator only ensures:
      - Sleeps grow exponentially over time
      - Stops after `timeout` seconds
      - Optionally adds jitter

    Usage:
        @exponential_backoff(timeout=10, initial_interval=0.0001)
        def stream_chunks():
            while not done():
                yield get_chunk()
                time.sleep(0.001)  # <-- This is now IGNORED; decorator controls sleep
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            next_sleep = initial_interval
            elapsed = 0
            # wrapped function is called in every interval
            while True:
                elapsed += next_sleep
                exponential = min(elapsed // initial_interval, 50)
                next_sleep = min(initial_interval * (factor**exponential), max_interval)
                logger.debug(f'exponential backup {elapsed}s/{timeout}')
                for data, should_stop in func(*args, **kwargs):
                    logger.debug(f'yielding data {data}')
                    if data:
                        yield data
                        next_sleep = 0  # we have data, no need to sleep
                    if should_stop:
                        return
                if jitter:
                    next_sleep *= 0.5 + random()  # → [0.5, 1.5)
                time.sleep(next_sleep)
                if elapsed >= timeout:
                    logger.debug(f'exponential backup timeout exceeded {timeout}s')
                    raise TimeoutError(f"{func.__name__} exceeded timeout of {timeout}s")

        return wrapper

    return decorator


from minibatch import Buffer
from minibatch.window import RelaxedTimeWindow


class FlushWindow(RelaxedTimeWindow):
    """A window that flushes all data in the buffer

    This is useful if you don't care when the data has been inserted, nor how many
    items are in the buffer. Use this if you want to flush the buffer every time
    you read it. This is the fastest way to process data. Specify size=N to limit
    each window to at most N items. If size=None or size=0 all buffered data is
    returned - caution, this may use large amounts of memory.
    """

    def __init__(self, stream_name, size=None, interval=None, **kwargs):
        super().__init__(stream_name, **kwargs)
        self.interval = interval if interval is not None else 0.01
        self.size = size or None

    def window_ready(self):
        last_read = datetime.utcnow()
        max_read = datetime.utcnow()
        return True, (last_read, max_read)

    def query(self, *args):
        last_read, max_read = args
        fltkwargs = dict(stream=self.stream_name, created__lte=last_read, processed=False)
        logger.debug(f'RelaxedTimeWindow.query {fltkwargs=}')
        qs = Buffer.objects.no_cache().filter(**fltkwargs)
        return qs if not self.size else qs.limit(self.size)

    def timestamp(self, *args):
        self.stream.modify(last_read=datetime.utcnow())
