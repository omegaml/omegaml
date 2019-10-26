
def enforce_logging_format(log_data):
    log_data = {
        'start_dt': log_data['start_dt'],
        'end_dt': log_data['end_dt'],
        'user': log_data['user'],
        'kind': log_data['kind'],
        'client_ip': log_data['client_ip'],
        'server_ip': log_data['server_ip'],
        'action': log_data['action'],
        'data': log_data['data'],
        'status': log_data['status'],
    }
    return log_data