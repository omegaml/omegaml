import json
import logging
from hashlib import pbkdf2_hmac
from time import sleep
from typing import Callable, Any, Dict
from uuid import uuid4

from jose import jwe

from minibatch.tests.util import LocalExecutor
from omegaml.util import tryOr, utcnow

logger = logging.getLogger(__name__)


class StreamableResourceMixin:
    def prepare_streaming_result(self, promise=None, stream=None, streamer=None):
        """ prepare result for event streaming

        Args:
            promise (celery.AsyncResult): a celery result to be resolved
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
        }  # type: Dict[str, Callable[[str], Any]]
        _default_streamer = STREAMERS.get('default')
        streaming_method = STREAMERS.get(streamer, _default_streamer)
        return streaming_method(stream)

    def de_inline_streaming(self, stream):
        class Sink(list):
            def put(self, chunks):
                self.extend(chunks)

            def __bool__(self):
                return True  # required to make work with minibatch

        om = self.om
        buffer = Sink()
        logger.debug("complete:stream_result getting stream")
        streaming = om.streams.getl(f'.system/complete/{stream}',
                                    executor=LocalExecutor(),
                                    sink=buffer)
        emitter = streaming.make(lambda window: window.data)
        has_chunks = lambda: emitter.stream.buffer().limit(1).count() > 0
        logger.debug("complete:stream_result waiting for status ")
        timeout = 1e6
        while timeout or has_chunks():
            timeout -= 1
            logger.debug("complete:stream_result waiting for chunks")
            emitter.run(blocking=False)
            for chunk in buffer:
                logger.debug("complete:stream_result chunk received: %s", chunk)
                data = chunk.get('result', chunk)
                yield data
                # TODO use a sentinel that is not tied to openai message format
                if data.get('finish_reason', '').startswith('stop'):
                    timeout = 0
            buffer.clear()
            sleep(0.01)
        logger.debug("done:stream_result closing response")

    def _handoff_to_ssechat(self, stream):
        # implement sse event streaming by handing off to streaming endpoint
        # TODO refactor into a StreamableResult so that we can have multiple implementations
        #      (e.g. direct response, redirect to sse endpoint, GRIP proxy etc.)
        def encrypt_payload(payload):
            session_id = uuid4().hex
            key = pbkdf2_hmac('sha256', b'password', str(session_id).encode('utf-8'), 500000)
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
            'created': utcnow().isoformat(),
        }
        cookies = make_secure_cookies(payload)
        return '', 302, {'Location': '/events/chat/completions'}, cookies
