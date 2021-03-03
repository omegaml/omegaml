import re

from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from .util import log_request


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
