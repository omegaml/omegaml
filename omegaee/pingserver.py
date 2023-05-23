from time import sleep

import json

import logging

import os
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

DEFAULT_PORT = 5000
DEFAULT_HOST = 'localhost'

class CeleryWorkerPingServer(Thread):
    """ A /healthz response server for celery workers

    Implements a localhost-bound HTTP server that responds to /healthz
    queries by pinging the local Celery worker. This is equivalent to, yet a lot faster
    and less resource consuming than calling `celery inspect ping`.

    Usage:
        # in tasks.py
        @celeryd_after_setup.connect
        def setup_ping_server(sender, instance, **kwargs):
            server = CeleryWorkerPingServer(instance)
            server.start()
            stop_ping_server.server = server

        @worker_shutting_down.connect
        def stop_ping_server(sig, how, exitcode, **kwargs):
            stop_ping_server.server.stop()

    How it works:
        Upon start up of a celery worker (the main process), CeleryWorkerPingServer
        starts a local HTTP server. The server responds to /healthz queries by
        sending a celery.inspect().ping() to the local worker instance. If the
        worker responds with a 'pong', the /healthz response is set to HTTP status
        200 (OK), if not it is set to 400 (Bad Request).

    Alternatives:
        https://github.com/celery/celery/issues/4079
    """
    def __init__(self, worker, port=None):
        super().__init__()
        # TODO make CELERY_PING_SERVER a host:port configurable, default to 0.0.0.0
        #      rationale: kubernetes health probes http-get do not work on localhost
        port = int(port or os.environ.get('CELERY_PING_SERVER') or DEFAULT_PORT)
        self.app = worker.app
        self.worker_name = worker.hostname
        if '@' not in self.worker_name:
            self.worker_name = f'celery@{self.worker_name}'
        self._server_address = (DEFAULT_HOST, port)
        self._server = HTTPServer(self._server_address,
                                  self.response_handler())
        self.logger = logging.getLogger(__name__)
        self.max_retry = 5

    def response_handler(self):
        server = self
        celeryapp = server.app

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                server.logger.info(f'starting celery ping to {server.worker_name}')
                for i in range(server.max_retry):
                    try:
                        # TODO: use control().ping(), with a shorter timeout
                        resp = celeryapp.control.inspect().ping(destination=[server.worker_name])
                    except Exception as e:
                        server.logger.error(f'got celery ping exception {e} in {i}/{server.max_retry} attempts')
                        resp = None
                        sleep(.5)
                    else:
                        server.logger.info(f'received ping response {resp}')
                        break
                status = 'ok' if resp and server.worker_name in resp else 'nok'
                self.respond(status)

            def respond(self, status):
                STATUS_MAP = {
                    'ok': 200,
                    'nok': 400,
                }
                message = json.dumps({'status': status})
                self.send_response(STATUS_MAP[status], status)
                self.end_headers()
                self.wfile.write(message.encode('utf8'))

        return Handler

    @property
    def url(self):
        hostname, port = self._server_address
        return f'http://{hostname}:{port}'

    def run(self):
        self.logger.info('starting celery ping server')
        self._server.running = True
        self._server.serve_forever()

    def stop(self):
        self.logger.info('shutting down ping server')
        self._server.shutdown()
        self._server.socket.close()
