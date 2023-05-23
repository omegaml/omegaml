import os

import logging
import re
import uuid
from contextlib import contextmanager
from django.conf import settings
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from time import perf_counter

from config.logutil import LoggingRequestContext
from .util import log_request

_default_loggable_re = r'/(api/.*|admin.*)/?'
logger = logging.getLogger('django')
loggable_requests = re.compile(os.environ.get('DJANGO_LOG_REQUESTS', _default_loggable_re))


class EventsLoggingMiddleware(MiddlewareMixin):
    """
    Custom middleware to log requests for selected resources
    """
    loggable_requests = re.compile(r'/api/.*/(model|dataset|job|script)(/.*)?')

    def process_request(self, request):
        # Add timestamp to request
        request.start_dt = timezone.now()
        request.logging_context = {}

    def process_response(self, request, response):
        # Log request if user is authenticated and this is for an api
        should_log = self.loggable_requests.match(request.path) is not None
        should_log &= hasattr(request, 'user') and request.user.is_authenticated
        if should_log:
            try:
                log_request(request, response)
            except Exception as e:
                pass
        return response


class RequestTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        _header_id = getattr(settings, 'REQUEST_ID_HEADER', 'X_REQUEST_ID').replace('-', '_')
        self.request_header_id = 'HTTP_{}'.format(_header_id)

    def track_context(self, request):
        LoggingRequestContext.inject(clientIP=request.get_host(),
                                     client=request.META.get('HTTP_USER_AGENT'))
        requestId = (getattr(request, '_requestid', None) or
                     request.META.get(self.request_header_id) or
                     uuid.uuid4().hex)
        setattr(request, '_requestid', requestId)

    def track_user(self, request):
        LoggingRequestContext.inject(user_id=getattr(request, 'user', None))

    @contextmanager
    def measure(self, request):
        start = perf_counter()
        yield
        stop = perf_counter()
        setattr(request, '_request_total', (stop - start) * 1000)

    def start_request(self, request):
        self.track_context(request)
        logger.debug(f'{request.method} {request.path}')

    def finalize_request(self, request, resp):
        self.track_user(request)
        should_log = loggable_requests.match(request.path) is not None
        if should_log:
            logger.info(f'{request.method} {request.path} {resp.status_code} {request._request_total:.2f}ms')

    def __call__(self, request):
        self.start_request(request)
        with self.measure(request) as m:
            resp = self.get_response(request)
        self.finalize_request(request, resp)
        return resp
