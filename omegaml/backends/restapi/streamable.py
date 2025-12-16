import json
import logging
import os
from hashlib import pbkdf2_hmac
from time import sleep
from typing import Callable, Any, Dict
from uuid import uuid4

from jose import jwe

from minibatch.tests.util import LocalExecutor
from omegaml.util import tryOr, utcnow

logger = logging.getLogger(__name__)


class StreamableResourceMixin:
    """ resource mixin to handle streaming results in line of by handing-off to a streaming server

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
    PBKDF_ITER = int(os.getenv('PBKDF_ITER', 500000))

    def prepare_streaming_result(self, promise=None, resource_name=None, raw=False, stream=None, streamer=None):
        """ prepare result for event streaming

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
        streamer = streamer or self.om.defaults.OMEGA_EVENTS_STREAMER
        # functions that handle streaming
        #    name => method(stream)
        STREAMERS = {
            'inline': self._inline_streaming,
            'ssechat': self._handoff_to_ssechat,
            'default': self._inline_streaming,
        }  # type: Dict[str, Callable[..., Any]]
        _default_streamer = STREAMERS.get('default')
        streaming_method = STREAMERS.get(streamer, _default_streamer)
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
        logger.debug("complete:stream_result getting stream")
        stream_name = f'.system/complete/{stream}'
        streaming = om.streams.getl(stream_name,
                                    executor=LocalExecutor(),
                                    sink=buffer,
                                    size=1, interval=0.01)
        # process stream, one message at a time
        # -- emitter to sink buffer
        emitter = streaming.make(lambda window: window.data)
        # -- check for new messages
        has_chunks = lambda: emitter.stream.buffer().limit(1).count() > 0
        logger.debug("complete:stream_result waiting for status ")
        # -- interval => frequency of stream checks, keep resource friendly (CPU, DB)
        # -- timeout => maximum time (in interval steps) without new messages
        interval = 0.0001  # sleep
        timeout = 10 // interval  # timeout in seconds, max
        has_error = False  # error flag, as indicated by chunks
        message = None  # final error message, used on has_error = True
        # -- process messages
        while timeout > 0 or has_chunks():
            timeout -= 1
            logger.debug("complete:stream_result waiting for chunks")
            emitter.run(blocking=False)
            for chunk in buffer:
                # determine if we should stop
                finish_reason = chunk.get('stream_complete', '')
                should_stop = finish_reason.startswith('stop')
                has_error = finish_reason.startswith('error')
                if should_stop or has_error:
                    timeout = 0
                    message = chunk.get('message', '')
                    break
                # process chunk by forwarding to Sink buffer
                logger.debug("complete:stream_result chunk received: %s", chunk)
                data = self.prepare_result(chunk, resource_name=resource_name)
                data.update(data.pop('result', {})) if raw else None
                yield data
            buffer.clear()
            sleep(interval)
        # -- done by timeout or end of messages, clear the stream
        emitter.stream.clear()
        om.streams.drop(stream_name, force=True)
        logger.debug("done:stream_result closing response")
        # propagate errors as RuntimeExceptions
        # -- allow failure to propagate to http service endpoint
        if has_error:
            raise RuntimeError(message)

    def _handoff_to_ssechat(self, stream, raw=False, resource_name=None):
        # implement sse event streaming by 302 redirect, handing off to streaming endpoint
        def encrypt_payload(payload):
            session_id = uuid4().hex
            # SEC: A256CGM is the recommended algorithm for JWE, https://datatracker.ietf.org/doc/html/rfc7518#section-5.1
            #      implementation of JWE by the python-jose package
            key = pbkdf2_hmac('sha256', self.SECRET_KEY.encode('utf-8'), str(session_id).encode('utf-8'),
                              self.PBKDF_ITER)
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
