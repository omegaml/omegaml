import logging
import re
from contextlib import contextmanager
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from time import perf_counter

from config.logutil import LoggingRequestContext
from .util import log_request

logger = logging.getLogger('django')


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


@contextmanager
def measure(request):
    start = perf_counter()
    logger.debug(f'{request.method} {request.path}')
    yield measure
    resp = measure.resp
    stop = perf_counter()
    total = (stop - start) * 1000
    LoggingRequestContext.inject(user=getattr(request, 'user'),
                                 clientIP=request.get_host(),
                                 client=request.META.get('HTTP_USER_AGENT'))
    logger.info(f'{request.method} {request.path} {resp.status_code} {total:.2f}ms')


class RequestTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        with measure(request) as m:
            resp = self.get_response(request)
            m.resp = resp
        return resp
