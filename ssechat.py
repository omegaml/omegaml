# app2.py
import json
import logging
import threading
from time import sleep

from flask import Flask, Response, request, abort

from minibatch.tests.util import LocalExecutor

app = Flask(__name__)
logger = app.logger

# disable dump of watchdog DEBUG messages on startup with debug=True
watchdog_logger = logging.getLogger('watchdog')
watchdog_logger.setLevel(logging.INFO)

# Sample words to send in the SSE stream
words = [f"word{i}" for i in range(1, 10)]

import omegaml as om

context = threading.local()


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

    def inner(*args, **kwargs):
        context.session_id = session_id = request.cookies.get('session_id')
        app.logger.info('session: %s', session_id)
        if not session_id:
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


@app.route('/events/chat/completions')
@authorized
def events_chat_completions():
    return Response(stream_result(context.session_id), content_type='text/event-stream')


@app.route('/test')
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


if __name__ == '__main__':
    app.run(port=5001, threaded=True, debug=True)
