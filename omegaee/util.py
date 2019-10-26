import socket
from datetime import datetime

from omegaml.celeryapp import app


def log_task(task, status):
    task_id = task.request.id
    task_start_dt = task.request.start_dt.isoformat()
    task_end_dt = datetime.now().isoformat()
        
    task_data = {
        'task_id': task_id,
    }
    if status != 'SUCCESS':
        task_result = task.AsyncResult(task_id)
        task_traceback = task_result.traceback
        task_data['task_traceback'] = task_traceback
       
    server_ip = socket.gethostbyname(socket.gethostname())

    task_log = {
        'start_dt': task_start_dt,
        'end_dt': task_end_dt,
        'user': task.request.user,
        'kind': 'task',
        'client_ip': '',
        'server_ip': server_ip,
        'action': task.name,
        'status': status,
        'data': task_data,
    }
    
    app.send_task('omegaops.tasks.log_event_task', (task_log,), queue='omegaops', retry_policy={
        'max_retries': 3,
        'interval_start': 0,
        'interval_step': 0.2,
        'interval_max': 0.2,
    })
