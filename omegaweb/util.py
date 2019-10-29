import socket

from django.utils import timezone
from whitenoise.storage import CompressedManifestStaticFilesStorage

# FIXME remove dependency on omegaops
from omegaops.celeryapp import app


class FailsafeCompressedManifestStaticFilesStorage(
    CompressedManifestStaticFilesStorage):
    """
    originally from landingpage
    """

    def post_process(self, *args, **kwargs):
        """
        make the collectstatic command ignore exceptions
        """
        files = super(CompressedManifestStaticFilesStorage, self).post_process(*args, **kwargs)
        for name, hashed_name, processed in files:
            if isinstance(processed, Exception):
                processed = False
            yield name, hashed_name, processed


def log_request(request, response):
    """
    Create log data from request and response objects
    """
    request_end = timezone.now()
    request_absolute_path = request.path
    request_uri = request.get_full_path()
    resolver = request.resolver_match
    request_app_name = resolver.app_name or ''
    request_namespaces = resolver.namespaces or []
    request_url_name = resolver.url_name or ''
    # For Tastypie resources
    request_resource_name = resolver.kwargs.get('resource_name', '')

    if 'HTTP_X_FORWARDED_FOR' in request.META:
        request_client_ip = request.META['HTTP_X_FORWARDED_FOR'].split(",")[0]
    else:
        request_client_ip = request.META['REMOTE_ADDR']

    server_ip = socket.gethostbyname(socket.gethostname())

    # Create request specific logs  
    request_data = {
        'request_absolute_path': request_absolute_path,
        'request_method': request.method,
        'request_app_name': request_app_name,
        'request_namespaces': request_namespaces,
        'request_url_name': request_url_name,
        'request_resource_name': request_resource_name,
    }
    # Add logging context data in request log
    request_data.update(request.logging_context)

    request_log = {
        'start_dt': request.start_dt.isoformat(),
        'end_dt': request_end.isoformat(),
        'user': request.user.username,
        'kind': 'request',
        'client_ip': request_client_ip,
        'server_ip': server_ip,
        'action': request_uri,
        'data': request_data,
        'status': response.status_code,
    }

    if app.conf.task_always_eager:
        # send_task in eager mode / without a broker running will wait forever
        from omegaops.tasks import log_event_task
        log_event_task(task, task_log)
    else:
        app.send_task('omegaops.tasks.log_event_task', (request_log,), queue='omegaops')


def get_api_task_data(task_result):
    task_data = {
        'task_id': task_result.task_id,
    }
    return task_data
