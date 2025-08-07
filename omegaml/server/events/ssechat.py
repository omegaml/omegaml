# consider alternative using pushpin
import json
import logging
import threading
from datetime import timedelta, datetime
from hashlib import pbkdf2_hmac
from time import sleep

from flask import Response, request, abort, Blueprint, current_app
from jose import jwe

from minibatch.tests.util import LocalExecutor
from omegaml.client.auth import AuthenticationEnv
from omegaml.util import utcnow

TIMEOUT = 100  # timeout in seconds

logger = logging.getLogger(__name__)

bp = Blueprint('ssechat', __name__)
context = threading.local()

auth_env = AuthenticationEnv.active()


def authorized(fn):
    """ decorator to authorize views

    Checks authorization cookie, aborts with HTTP 401 if not present or could not
    be authenticated. Otherwise calls the view function as is.

    Usage:
        @app.route('/foo')
        @authorized
        def myview():
            return ...
    """

    def decode_payload():
        context.session_id = session_id = request.cookies.get('session_id')
        key = pbkdf2_hmac('sha256', b'password', str(session_id).encode('utf-8'), 500000)
        token = request.cookies.get('token')
        logger.debug(f'key {key}')
        logger.debug(f'token {token}')
        context.payload = payload = json.loads(jwe.decrypt(token, key))
        return session_id, payload

    def verify(session_id, payload):
        context.request_initiated = datetime.fromisoformat(payload.get('created', utcnow().isoformat()))
        context.request_timeout = context.request_initiated + timedelta(seconds=TIMEOUT)
        context.message_valid = context.request_timeout >= utcnow()
        context.authenticated = bool(session_id)
        return context.message_valid and context.authenticated

    def inner(*args, **kwargs):
        # api backend:
        # --  must set a salt (e.g. random 16 byte id is the salt)
        # -- derive a key from a shared password + salt, env.OMEGA_EVENTS_KEY
        # -- encode the session_id (= task id) using a JWE payload
        # -- the payload should contain the creation datetime + timeout
        # sse server:
        # -- get the salt
        # -- derive key from shared password + salt
        # -- decode the JWE payload and get the session_id
        # -- check on creation datetime + timeout < current time
        # this way we have a secure transfer from the backend to the sse server
        # -- even if the encrypted payload gets stolen, it can't be decoded without the shared password
        # -- using a salt means every payload results in a different cipher text, even if the payload is the same
        # -- the JWE can't be modified because it is signed
        # -- token becomes useless after timeout
        context.auth = None  # get real auth
        context.om = auth_env.get_omega_from_apikey(auth=context.auth)
        session_id, payload = decode_payload()
        verified = verify(session_id, payload)
        current_app.logger.info('session: %s is verified %s', session_id, verified)
        if not verified:
            abort(401)
        return fn(*args, **kwargs)

    return inner


def sse_json(fn):
    """ convert generator result to valid HTTP server-side event (SSE)

    Usage:
        decorate a generator function as @sse_json, it will convert
        the data returned to a json-formatted SSE data message

        @sse_json
        def myfunc:
            for data in buffer:
                yield data # must be a dict

    See Also:
        https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events#sending_events_from_the_server
    """

    def inner(*args, **kwargs):
        for data in fn(*args, **kwargs):
            message = json.dumps(data)
            yield f"data: {message}\n\n"
            logger.debug("sent:stream_result chunk sent: %s", data)

    return inner


@sse_json
def stream_result(key):
    class Sink(list):
        def put(self, chunks):
            self.extend(chunks)

        def __bool__(self):
            return True  # required to make work with minibatch

    om = context.om
    buffer = Sink()
    logger.debug("complete:stream_result getting stream")
    streaming = om.streams.getl(f'.system/complete/{key}',
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


@bp.route('/events/chat/completions')
@authorized
def events_chat_completions():
    payload = context.payload
    stream = payload.get('stream')
    return Response(stream_result(stream), content_type='text/event-stream')


@bp.route('/test')
def perftest():
    # use this to test performance of threaded v.s. unthreaded
    # -- threaded=False will increase p50 latency per request
    # -- threaded=True will keep p99 latency at approx 1.0s
    # usage:
    #    $ python ssechat.py
    #    $ ali http://localhost:5001/test -r 50
    # -- ali source: https://github.com/nakabonne/ali
    # this will send 50 requests/second
    sleep(1.0)
    return 'OK'
