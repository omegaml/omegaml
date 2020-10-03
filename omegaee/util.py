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

    if task.request.is_eager:
        # send_task in eager mode, without a broker running, would wait forever
        from omegaops.tasks import log_event_task
        log_event_task(task_log)
    else:
        # note the user's omegaops queue is shovelled to the omops user for actual logging
        # see omops.create_ops_forwarding_shovel
        task.app.send_task('omegaops.tasks.log_event_task', (task_log,), queue='omegaops')
        pass
