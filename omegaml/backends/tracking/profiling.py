from omegaml.backends.tracking.simple import OmegaSimpleTracker


class BackgroundProfiler:
    """ Profile CPU, Memory and Disk use in a background thread
    """

    def __init__(self, interval=10, callback=print):
        self._stop = False
        self._interval = interval
        self._callback = callback
        self._metrics = ['cpu', 'memory', 'disk']

    def profile(self):
        """
        returns memory and cpu data as a dict
            memory_load (float): percent of total memory used
            memory_total (float): total memory in bytes
            cpu_load (list): cpu load in percent, per cpu
            cpu_count (int): logical cpus,
            cpu_freq (float): MHz of current cpu frequency
            cpu_avg (list): list of cpu load over last 1, 5, 15 minutes
            disk_use (float): percent of disk used
            disk_total (int): total size of disk, bytes
        """
        import psutil
        from datetime import datetime as dt
        p = psutil
        disk = p.disk_usage('/')
        cpu_count = p.cpu_count()
        data = {'profile_dt': dt.utcnow()}
        if 'memory' in self._metrics:
            data.update(memory_load=p.virtual_memory().percent,
                        memory_total=p.virtual_memory().total)
        if 'cpu' in self._metrics:
            data.update(cpu_load=p.cpu_percent(percpu=True),
                        cpu_count=cpu_count,
                        cpu_freq=[f.current for f in p.cpu_freq(percpu=True)],
                        cpu_avg=[x / cpu_count for x in p.getloadavg()])
        if 'disk' in self._metrics:
            data.update(disk_use=disk.percent,
                        disk_total=disk.total)
        return data

    @property
    def interval(self):
        return self._interval

    @interval.setter
    def interval(self, interval):
        self._interval = interval
        self.stop()
        self.start()

    @property
    def metrics(self):
        return self._metrics

    @metrics.setter
    def metrics(self, metrics):
        self._metrics = metrics

    def start(self):
        """ runs a background thread that reports stats every interval seconds

        Every interval, calls callback(data), where data is the output of BackgroundProfiler.profile()
        Stop by BackgroundProfiler.stop()
        """
        import atexit
        from threading import Thread
        from time import sleep

        def runner():
            cb = self._callback
            try:
                while not self._stop:
                    cb(self.profile())
                    sleep(self._interval)
            except (KeyboardInterrupt, SystemExit):
                pass

        # handle exits by stopping the profiler
        atexit.register(self.stop)
        # start the profiler
        self._stop = False
        t = Thread(target=runner)
        t.start()
        # clean up
        atexit.unregister(self.stop)

    def stop(self):
        self._stop = True


class OmegaProfilingTracker(OmegaSimpleTracker):
    """ A metric tracker that runs a system profiler while the experiment is active

    Will record ``profile`` events that contain cpu, memory and disk profilings.
    See BackgroundProfiler.profile() for details of the profiling metrics collected.

    Usage:

        To log metrics and system performance data::

            with om.runtime.experiment('myexp', provider='profiling') as exp:
                ...

            data = exp.data(event='profile')

    Properties::

        exp.profiler.interval = n.m # interval of n.m seconds to profile, defaults to 3 seconds
        exp.profiler.metrics = ['cpu', 'memory', 'disk'] # all or subset of metrics to collect
        exp.max_buffer = n # number of items in buffer before tracking

    Notes:
        - the profiling data is buffered to reduce the number of database writes, by
          default the data is written on every 6 profiling events (default: 6 * 10 = every 60 seconds)
        - the step reported in the tracker counts the profiling event since the start, it is not
          related to the step (epoch) reported by e.g. tensorflow
        - For every step there is a ``event=profile``, ``key=profile_dt`` entry which you can use
          to relate profiling events to a specific wall-clock time.
        - It usually sufficient to report system metrics in intervals > 10 seconds since machine
          learning algorithms tend to use CPU and memory over longer periods of time.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile_logs = []
        self.max_buffer = 10

    def log_profile(self, data):
        """ the callback for BackgroundProfiler """
        self.profile_logs.append(data)
        if len(self.profile_logs) >= (self.max_buffer or 1):
            self.flush()

    def flush(self):
        super().flush()

        def log_items():
            for step, data in enumerate(self.profile_logs):
                # record the actual time instead of logging time (avoid buffering delays)
                dt = data.get('profile_dt')
                for k, v in data.items():
                    item = self._common_log_data('profile', k, v, step=step, dt=dt)
                    yield item

        if self.profile_logs:
            # passing list of list, as_many=True => collection.insert_many() for speed
            self._store.put([item for item in log_items()], self._data_name,
                            index=['event'], as_many=True, noversion=True)
            self.profile_logs = []

    def start_runtime(self):
        self.profiler = BackgroundProfiler(callback=self.log_profile)
        self.profiler.start()
        super().start_runtime()

    def stop_runtime(self):
        self.profiler.stop()
        self.flush()
        super().stop_runtime()
