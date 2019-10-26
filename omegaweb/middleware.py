from django.utils import timezone

from .util import log_request


class EventsLoggingMiddleware:
    """
    Custom middleware to log requests for selected resources
    """
    def process_request(self, request):
        # Add timestamp to request
        request.start_dt = timezone.now()
        request.logging_context = {}

    def process_response(self, request, response):
        # Log request if user is authenticated
        if hasattr(request, 'user') and request.user.is_authenticated():
            try:
                log_request(request, response)
            except Exception as e:
                return response
        return response
