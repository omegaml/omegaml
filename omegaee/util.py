import logging
import os
import socket
from datetime import datetime


def log_task(task, status, exception=None):
    from datetime import datetime as dt

    task_start_dt = task.request.get('start_dt', dt.now()).isoformat()
    task_end_dt = datetime.now().isoformat()

    task_id = task.request.id
    server_ip = socket.gethostbyname(socket.gethostname())
    username = getattr(task.request, 'user', None)

    task_data = {
        'task_id': task_id,
        'exception': str(exception) if exception else None,
    }

    task_log = {
        'start_dt': task_start_dt,
        'end_dt': task_end_dt,
        'user': username,
        'client_hostname': task.request.origin,
        'server_hostname': task.request.hostname,
        'kind': 'task',
        'client_ip': '',
        'server_ip': server_ip,
        'action': task.name,
        'status': status,
        'data': task_data,
    }

    if os.environ.get('OMEGA_ENABLE_TASK_LOGGING'):
        if task.request.is_eager:
            # send_task in eager mode, without a broker running, would wait forever
            from omegaops.tasks import log_event_task
            log_event_task(task_log)
        else:
            # note the user's omegaops queue is shovelled to the omops user for actual logging
            # see omops.create_ops_forwarding_shovel
            task.app.send_task('omegaops.tasks.log_event_task', (task_log,), queue='omegaops')
            pass


class HostnameInjectingFilter(logging.Filter):
    def __init__(self):
        self.hostname = socket.gethostname()

    def filter(self, record):
        record.hostname = self.hostname
        return True


class TaskInjectingFilter(logging.Filter):
    def filter(self, record):
        from celery._state import get_current_task
        task = get_current_task()
        if task and task.request:
            record.__dict__.update(task_id=task.request.id,
                                   task_name=task.name,
                                   user_id=getattr(task, 'current_userid', '???'))
        else:
            record.__dict__.setdefault('task_name', '???')
            record.__dict__.setdefault('task_id', '???')
        return True


hostnameFilter = lambda *args, **kwargs: HostnameInjectingFilter()
taskFilter = lambda *args, **kwargs: TaskInjectingFilter()
