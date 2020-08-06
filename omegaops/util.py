import time
from functools import wraps


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


def retry(ExceptionToCheck, tries=4, delay=3, backoff=2, logger=None):
    """Retry calling the decorated function using an exponential backoff.

    http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/
    original from: http://wiki.python.org/moin/PythonDecoratorLibrary#Retry

    :param ExceptionToCheck: the exception to check. may be a tuple of
        exceptions to check
    :type ExceptionToCheck: Exception or tuple
    :param tries: number of times to try (not retry) before giving up
    :type tries: int
    :param delay: initial delay between retries in seconds
    :type delay: int
    :param backoff: backoff multiplier e.g. value of 2 will double the delay
        each retry
    :type backoff: int
    :param logger: logger to use. If None, print
    :type logger: logging.Logger instance
    """

    def deco_retry(f):

        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except ExceptionToCheck as e:
                    msg = "%s, Retrying in %d seconds..." % (str(e), mdelay)
                    if logger:
                        logger.warning(msg)
                    else:
                        print(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return f(*args, **kwargs)

        return f_retry  # true decorator

    return deco_retry


def purge_result_queues(max=None):
    """
    Utility function to purge result queues

    Use to combat high memory water mark (mnesia overloaded)

    Celery creates a new queue for every message stored in the ampq:// results
    backend. Every queue consumes some memory, resulting in excessive memory
    usage by Rabbitmq.

    This is a short-term hack only. It is better to apply below remedies.
    Since the number of queues can be very high and it can take quite some time
    to delete all queues, this function displays a progress indicator while
    the deletion is in progress.

    Remedies:
        - Use CELERY_TASK_RESULT_EXPIRES to reduce the timeout for automatic deletion
        - Use another results backend than ampq, e.g. Redis or Mongo

    See:
        http://www.pythondoc.com/celery-3.1.11/configuration.html#celery-task-result-expires

    Args:
        max: the number of queues to delete

    Returns:
        None
    """
    import pyrabbit2 as rmq
    import tqdm
    from omegaml.util import urlparse, settings as get_settings

    defaults = get_settings()
    parsed = urlparse.urlparse(defaults.OMEGA_BROKERAPI_URL)
    host = '{}:{}'.format(parsed.hostname, parsed.port)
    username = parsed.username
    password = parsed.password
    client = rmq.Client(host, username, password)
    bindings = client.get_bindings()
    result_queus = [b['destination'] for b in bindings if b['source'] == 'celeryresults']
    for i, rq in tqdm.tqdm(enumerate(result_queus)):
        if max and i > max:
            break
        try:
            client.delete_queue('/', rq)
        except Exception as e:
            print("warning {}".format(e))
