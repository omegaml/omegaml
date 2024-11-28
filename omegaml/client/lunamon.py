from __future__ import absolute_import

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import atexit
import logging
import os
import pymongo
import weakref
from datetime import datetime
from omegaml.util import inprogress
from time import sleep
from yaspin import yaspin


class LunaMonitor:
    """ a simple effective monitor that runs checks in the background

    Usage:
        from omegaml.client.lunamon import LunaMonitor
        from omegaml import Omega
        om = Omega()
        monitor = LunaMonitor(checks=OmegaMonitors.on(om))
        monitor.assert_ok('health')
        monitor.stop()

    Args:
        om (Omega): the Omega instance to monitor
        interval (int): the interval in seconds to run checks, defaults to 60
        timeout (int): the timeout in seconds for each check, defaults to 5
        checks (dict): the checks to run, defaults to a set of built-in checks,
           'check' => fn, where fn is a callable that returns True or None if the
           check is ok
        on_error (callable): the callback to call on error, defaults to None, the
              callback is a function that takes status (dict) as argument
        on_status (callable): the callback to call on status, defaults to None, the
              callback is a function that takes status (dict) as argument

    Returns:
        LunaMonitor: the monitor instance

    Notes:
        -
    """
    _ALL_MONITORS = []
    DEFAULT_INTERVAL = 15  # the interval in seconds to run all checks
    DEFAULT_CHECK_TIMEOUT = 5  # the timeout in seconds for each check

    def __init__(self, interval=None, timeout=None, checks=None, on_error=None, on_status=None):
        self.checks = LunaMonitorChecks.on(self)
        self.checks.update(checks or {})
        self.interval = interval if interval is not None else self.DEFAULT_INTERVAL
        self.timeout = timeout if timeout is not None else self.DEFAULT_CHECK_TIMEOUT
        self.check_timeout = self.DEFAULT_CHECK_TIMEOUT
        self._logger = logging.getLogger(__name__)
        self._logger.propagate = False
        if os.environ.get('LUNA_DEBUG'):
            self._logger.addHandler(logging.StreamHandler())
            self._logger.setLevel(logging.DEBUG)
        self._status = {}
        self._buffer = defaultdict(list)
        self._callbacks = {
            'error': [on_error] if on_error else [],
            'status': [on_status] if on_status else []
        }
        self._max_buffer = 2 * 3600 // self.interval  # max entries to keep in buffer, per check
        self._start_monitor()

    def __del__(self):
        self.stop(wait=False)

    def status(self, check=None, data=False, by_status=False):
        """ get the status of a check

        Args:
            check (str|list): the check to get the status for, or None to get all,
               or a list of checks
            data (bool): if True, return the full status dict, otherwise return just
               the status as one of 'ok', 'failed'. Defaults to False
            by_status (bool): if True, return the status as a dict of status => [check, ...],
               else return the status as a dict check => status. Defaults to False. Only
               applies if check is a list or None

        Returns:
            (dict|str): the status for each check
                - dict: the status of multiple checks (if check= is a list),
                        check => 'status' (ok|failed|pending) for by_status=False (default),
                        'status' => ['check', ...] for by_status=True
                - str: the status of a single check (if check= is a str)
        """
        checks = [check] if isinstance(check, str) else (check or self.checks.keys())
        report = {c: (self._status[c]['status']
                      if not data else dict(self._status[c]))
                  for c in checks if c != 'healthy'}
        if by_status:
            data, report = report, defaultdict(list)
            for check, status in data.items():
                report[status].append(check)
        else:
            report = report[check] if isinstance(check, str) else report
        return report

    def failed(self):
        """ get all failed checks

        Returns:
            list: the checks that failed
        """
        return [c for c in self.checks if self._status.get(c, {}).get('status') != 'ok']

    def stop(self, wait=False):
        self._logger.debug(f'setting monitor stop event, wait={wait}')
        LunaMonitor._stop_monitor(monitor=self, wait=wait)
        self._buffer.clear()

    @classmethod
    def stop_all(cls):
        if not cls._ALL_MONITORS:
            return

        @inprogress('exiting...')
        def _do_stop():
            for monitor in cls._ALL_MONITORS:
                try:
                    monitor.stop(wait=False)
                except ReferenceError:
                    # ignore weakref that has already been garbage collected
                    pass
            cls._ALL_MONITORS.clear()

        _do_stop()

    @property
    def active(self):
        return self._monitor_thread.is_alive() and not self._stop.is_set()

    def assert_ok(self, check=None, timeout=None):
        from time import sleep
        checks = [check] if isinstance(check, str) else (check or self.checks.keys())
        timeout = timeout if timeout is not None else 0
        check_ok = lambda c: self._status.get(c, {}).get('status') == 'ok'
        all_checks_ok = lambda: all(check_ok(c) for c in checks)
        while not all_checks_ok() and timeout > 0:
            sleep(.1)
            timeout -= .1
        if not all_checks_ok():
            raise AssertionError(f'checking {checks} failed due to {self.failed()} failing')
        return True

    def healthy(self, check=None, timeout=0, ignore=None):
        """ check if all checks are ok

        Args:
            check (str|list): the check to get the status for, or None to get all,
               or a list of checks
            timeout (float): the timeout to wait for the check to be ok, defaults to 0

        Returns:
            bool: True if all checks are ok, False otherwise
        """
        ignore = [ignore] if isinstance(ignore, str) else (ignore or [])
        checks = check or [k for k in self.checks.keys() if k not in ignore]
        try:
            self.assert_ok(checks, timeout=timeout)
        except AssertionError:
            return False
        return True

    def wait_ok(self):
        """ wait until all checks are ok

        Returns:
            None
        """
        with yaspin(text='waiting for checks to be ok', color='yellow') as t:
            while not self.healthy():
                services = ','.join(self.failed())
                t.text = f"waiting for dependencies {services}"
                sleep(.5)

    def notify(self, on_error=None, on_status=None):
        """ add a callback to be notified on error or status

        Registers a callback to be called on error or status. The callback
        will be called with the status as argument.

        Args:
            on_error (callable): the callback to call on error
            on_status (callable): the callback to call on status

        Returns:
            None
        """
        if on_error:
            self._callbacks['error'].append(on_error)
        if on_status:
            self._callbacks['status'].append(on_status)

    def add_check(self, name, fn):
        """ add a check to the monitor

        Args:
            name (str): the name of the check
            fn (callable): the function to call for the check
        """
        self.checks[name] = fn

    def drop_check(self, name):
        """ drop a check from the monitor

        Args:
            name (str): the name of the check to drop
        """
        self.checks.pop(name)

    def _start_monitor(self):
        from threading import Thread, Event
        self._logger.debug('starting monitor')
        # initialize status for all checks
        for check in self.checks:
            self._record_status(check, 'pending')
        # initialize monitor loop
        self._stop = Event()
        # -- start as a deamon thread to enable killing it on SystemExit
        self._monitor_thread = Thread(target=self._run_monitor_loop, daemon=True)
        # -- thread pool for running checks, this is a separate pool to avoid cpu overload
        self._check_pool = ThreadPoolExecutor(max_workers=len(self.checks) * 2)
        self._monitor_thread.start()
        # ensure we stop the monitor on exit, gc
        self._ALL_MONITORS.append(weakref.proxy(self))
        # TODO adopt to common finalizer pattern (see OmegaStore)
        # -- passing self causes refcount increase on LunaMonitor, thus won't be gc'd until sys exit
        weakref.finalize(self, self._stop_monitor, self, wait=False)

    @staticmethod
    def _stop_monitor(monitor, wait=False):
        monitor._logger.debug(f'monitor {monitor} stopping, wait={wait}')
        monitor._stop.set()
        # https://stackoverflow.com/a/49992422/890242
        # concurrent.futures.thread._threads_queues.clear()
        monitor._check_pool.shutdown(wait=wait, cancel_futures=True)
        monitor._logger.debug('monitor has shutdown')

    def _run_monitor_loop(self):
        self._logger.debug(f'monitor starting, running checks every {self.interval} seconds')
        i = 0
        status = {}
        while i == 0 or not self._stop.wait(timeout=self.interval):
            if self._stop.is_set():
                break
            self._logger.debug(f'monitor iteration {i}')
            try:
                self._run_checks()
            except (SystemExit, KeyboardInterrupt):
                self._logger.debug('monitor exit due to SystemExit')
                status = self._record_status('monitor', 'exit', exc=e)
                self.stop()
                break
            except (Exception, RuntimeError) as e:
                self._logger.debug('monitor failed', exc_info=True)
                status = self._record_status('monitor', 'failed', exc=e)
                self.stop()
                break
            else:
                status = self._record_status('monitor', 'ok')
            finally:
                self._forward_status(status)
            i += 1
        self._logger.debug(f'monitor exit, ran {i} check iterations')

    def _run_checks(self, checks=None):
        self._logger.debug('running checks')
        for check, fn in (checks or self.checks.items()):
            self._logger.debug(f'submitting check {check} on {fn.__self__.resource} using {fn}')
            if self._stop.wait(timeout=0):
                break
            # add decorators to fn
            # -- jitter to avoid thundering herd problem
            # -- time the function
            # -- ensure the function is callable with or without arguments
            fn = self._jitter(self._timed(self._safe_callable(fn)))
            # run check in a separate thread
            future = self._check_pool.submit(fn, monitor=self, check=check)
            # add a callback on success or failure
            # -- a single lambda is created for each check and future,
            #    thus we bind each check/future's actual values, not the loop vars
            recorder = (lambda c, f: lambda f: self._record_status_from_future(c, f))
            future.add_done_callback(recorder(check, future))
        self._logger.debug('done running checks')

    def _record_status_from_future(self, check, future):
        try:
            elapsed, rc = future.result()
        except Exception as e:
            rc = False
            elapsed, exc = e.args if len(
                e.args) else 0, e  # _timed() re-raises user exception as Exception(elapsed, exc)
        else:
            exc = None
        if bool(rc) or rc is None and not exc:
            # bool(rc) is True or None and no exception was raised, i.e. successful
            data = rc if not isinstance(rc, bool) else None  # allow for data to be returned
            exc = None
            status = 'ok'
            msg = f'check {check} was successful'
            rc = 0
        elif bool(rc) is False or exc:
            # bool(rc) is False or an exception was raised, i.e. failed
            status = 'failed'
            msg = f'check {check} failed with {exc}'
            data = rc
            rc = 1
        else:
            # we should never get here
            status = 'failed'
            msg = f'check {check} failed with {exc} and rc={rc} [weird]'
            data = rc
            rc = 9
        self._record_status(check, status, msg=msg, exc=exc, rc=rc, data=data, elapsed=elapsed)

    def _record_status(self, check, status, msg=None, exc=None, rc=None, data=None, elapsed=None):
        status = self._status[check] = {
            'status': status,
            'rc': rc,
            'message': msg if msg is not None else str(rc) if rc else None,
            'error': str(exc) if exc else None,
            'timestamp': datetime.utcnow().isoformat(),
            'elapsed': elapsed,
            'data': data,
        }
        self._buffer[check].append(status)
        if len(self._buffer[check]) > self._max_buffer:
            self._buffer[check].pop(0)
        self._logger.debug(f'recording status for {check} as {status}')
        # forward a copy of the status so our buffer cannot be modified
        status = dict(status)
        status['check'] = check
        # TODO add a timeout so we don't block on forwarding failures
        self._forward_status(status)
        return status

    def _forward_status(self, status):
        try:
            state = status['status']
            if state in ('ok', 'failed'):
                for cb in self._callbacks['status']:
                    cb(status)
            if state == 'failed':
                for cb in self._callbacks['error']:
                    cb(status)
        except Exception as e:
            self._logger.exception(f'failed to forward status {status} due to {e}')
        else:
            self._logger.debug(f'forwarded status {status} ok')

    def _jitter(self, fn):
        # add jitter to avoid thundering herd problem
        def _w(*args, **kwargs):
            import random
            from time import sleep
            jitter = random.uniform(0.01, 1.0)
            sleep(jitter)
            return fn(*args, **kwargs)

        return _w

    def _timed(self, func):
        # time a function and return elapsed time in seconds
        # https://stackoverflow.com/a/57561056/890242
        def _w(*a, **k):
            import time
            then = time.time()
            elapsed = lambda: time.time() - then
            try:
                res = func(*a, **k)
            except Exception as e:
                raise Exception(elapsed(), e)
            return elapsed(), res

        return _w

    def _safe_callable(self, fn):
        # try calling the check function with arguments, fallback to
        # calling without arguments
        def _w(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                return fn()

        return _w


class LunaMonitorChecks:
    """ checks to run for LunaMonitor itself

    This is a base class for checks to run for LunaMonitor. It provides
    a simple interface to run checks on a resource. The checks are simple
    methods that return True if the check is ok, False otherwise. Checks
    may also throw exceptions, in which case the check is considered failed.

    Usage:
        from omegaml.client.lunamon import LunaMonitorChecks

        class MyResourceMonitor(LunaMonitorChecks):
            def check_database(self, monitor=None, **kwargs):
                # ... some check
                return self.resource.database.ping()

        resource = ... # some object
        checks = MyResourceMonitor.on(resource)
        monitor = LunaMonitor(checks=checks)
        monitor.assert_ok('database')

    Notes:
        * the check methods must be named check_<name> where <name> is the check's name
          (e.g. check_database). You can override the cls.method_prefix attribute to change the
          prefix, defaults to 'check_'
        * the check methods may take a monitor= argument to access the monitor instance
        * the monitor will add the check as '<name>' to the monitor instance, i.e.
          monitor.status() will return the status of the check as 'name' => 'status'
        * the check methods can access the resource passed to LunaMonitorChecks.on(<resource>)
          via self.<resource_var>. You can override the cls.resource_var attribute to change
          the variable name, defaults to 'resource'
    """
    resource_var = 'resource'  # the self.<resource_var> to use for the resource
    method_prefix = 'check_'  # the method prefix to use for check methods

    def __init__(self, resource=None, prefix=None):
        # the rationale to use weakref is to avoid circular references (monitor -> resource -> monitor)
        self.resource = weakref.proxy(resource)
        self.method_prefix = prefix or self.method_prefix
        setattr(self, self.resource_var, self.resource) if self.resource_var != 'resource' else None

    @classmethod
    def on(cls, obj=None, prefix=None):
        self = cls(obj, prefix=prefix)
        return {
            k.replace(self.method_prefix, ''): getattr(self, k) for k in dir(self)
            if k.startswith(self.method_prefix)
        }

    def check_monitor(self, monitor=None, **kwargs):
        return monitor.active

    def check_health(self, monitor=None, **kwargs):
        return monitor.healthy(ignore='health')


class OmegaMonitors(LunaMonitorChecks):
    """ Luna monitors to run for omegaml instances """
    resource_var = 'om'

    def check_stores(self):
        with pymongo.timeout(1):
            self.om.datasets.list()

    def check_runtime(self):
        with pymongo.timeout(1):
            if self.om.runtime.celeryapp.conf.get('CELERY_ALWAYS_EAGER'):
                # local runtime in principle always works
                # -- however broker may still fail
                # -- hence we check the broker instead
                self.om.runtime.celeryapp.control.ping()
                loadavg = os.getloadavg()
                workers = [{
                    'name': 'local',
                    'status': 'running',
                    'activity': f'{loadavg[0]}% / 1',
                }]
            else:
                # -- for a remote runtime we submit a ping
                self.om.runtime.ping(timeout=5, source='monitor')
                status = self.om.runtime.status()
                workers = [{
                    'name': worker,
                    'status': 'running' if len(info['processes']) > 0 else 'idle',
                    'activity': f'{info["loadavg"][0]}% / {len(info["processes"])}',
                } for worker, info in status.items()]
            return workers

    def check_database(self, monitor=None, **kwargs):
        with pymongo.timeout(monitor.timeout):
            self.om.datasets.mongodb.command('ping')

    def check_broker(self):
        with pymongo.timeout(1):
            self.om.runtime.celeryapp.control.ping()


# register atexit handler to stop all monitors
atexit.register(LunaMonitor.stop_all)
