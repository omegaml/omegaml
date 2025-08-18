# consider alternative using pushpin
import json
import logging
import threading
from datetime import timedelta, datetime
from flask import Response, request, abort, Blueprint, current_app
from hashlib import pbkdf2_hmac
from jose import jwe
from time import sleep
from uuid import uuid4

from omegaml.backends.restapi.streamable import StreamableResourceMixin
from omegaml.client.auth import AuthenticationEnv
from omegaml.util import utcnow

TIMEOUT = 100  # timeout in seconds

logger = logging.getLogger(__name__)

bp = Blueprint('ssechat', __name__)
context = threading.local()

auth_env = AuthenticationEnv.active()


class Streamable(StreamableResourceMixin):
    def __init__(self, om):
        self.om = om


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

    # api backend:
    # -- must set a salt (e.g. random 16 byte id is the salt)
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

    def decode_payload():
        context.session_id = session_id = request.cookies.get('session_id')
        key = pbkdf2_hmac('sha256', Streamable.SECRET_KEY.encode('utf-8'), str(session_id).encode('utf-8'),
                          Streamable.PBKDF_ITER)
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
        try:
            session_id, payload = decode_payload()
            verified = verify(session_id, payload)
        except:
            abort(401)
        context.auth = payload.get('auth')
        context.om = auth_env.get_omega_for_task(_task(session_id), auth=context.auth)
        current_app.logger.info('session: %s is verified %s', session_id, verified)
        if not verified:
            abort(401)
        return fn(*args, **kwargs)

    def _task(session_id):
        class DummyTask:
            def __init__(self, id=None):
                self.system_kwargs = {}
                self.id = id or uuid4().hex

        return DummyTask(session_id)

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
    streamable = Streamable(context.om)
    for chunk in streamable.prepare_streaming_result(stream=key, raw=True, streamer='inline'):
        yield chunk


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
