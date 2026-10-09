Logging runtime execution
=========================

.. contents::

How it works
------------

When running tasks in the cloud it can be difficult to get access to
the technical log messages issued by the runtime or the model framework.
omega-ml provides straight access to logs that are created while a task is run.
This works independent of where the task is run (e.g. locally, on a CPU or a
GPU node, on-premise or in a cloud-provider etc.)

.. code:: python

    In [1]: # enable logging
            om.runtime.mode(logging=True)
            # run a task
            om.runtime.ping(fox='bar')
            # access the log
            om.logger.dataset.get()
    Out[2]:
        level  levelno   logger                                                msg                                               text hostname                 created
    0  SYSTEM      999   system                                           log init                                           log init    eowyn 2021-11-22 17:15:10.234
    1    INFO        4   simple  omega log: running ping task {'message': 'ping...  2021-11-22 17:15:10.410605 INFO omega log: run...    eowyn 2021-11-22 17:15:10.410
    2    INFO       20   celery  python log: running ping task {'message': 'pin...  2021-11-22 18:15:10,427 - celery - INFO - pyth...    eowyn 2021-11-22 17:15:10.427
    3    INFO       20  omegaml  package log: running ping task {'message': 'pi...  2021-11-22 18:15:10,428 - omegaml - INFO - pac...    eowyn 2021-11-22 17:15:10.428
    4    INFO       20     root  print log: running ping task {'message': 'ping...  2021-11-22 18:15:10,428 - root - INFO - print ...    eowyn 2021-11-22 17:15:10.428


Logging in scripts or jobs
--------------------------

Use logging in your own scripts or notebooks to log arbitrary information.

.. code:: python

    In [1]: # in your notebook
            logger = om.logger.getLogger('mylogger')
            logger.info('some message')

    In [2]: # access the log on any omegaml client
            om.logger.dataset.get(logger='mylogger')
    Out [3]:
    0   INFO        4  mylogger some message       2021-11-22 17:20:21.691137 INFO some message    eowyn 2021-11-22 17:20:21.691


Profiling execution
-------------------

We can use omega-ml tracking to measure any code execution on the runtime.
Say we want to understand the CPU load the following code generates:

.. code:: python

    # notebook testcpu
    import numpy as np
    import omegaml as om
    A = np.random.rand(10000, 10000)
    B = np.random.rand(10000, 10000)
    C = np.matmul(A, B)

We can profile the cpu and memory by wrapping the call to om.runtime as
an experiment using the :code:`profiling` tracking provider:

.. code:: python

    with om.runtime.experiment('perf', provider='profiling') as exp:
        om.runtime.job('testcpu').run().get()

This instructs the runtime worker, locally or on a remote machine,
to run the code and collect metrics on cpu, memory and disk usage. Once
the job is finished, the metrics can be accessed by getting back the
data as follows. Note that this tracks the data every time your code
is run so it is easy to compare different runs.

.. code::

    exp.data()
    =>
           experiment  run         event                          dt   node  step                       key                                              value
    0        perf    1         start  2021-11-25T10:11:23.538108  eowyn   NaN                       NaN                                                NaN
    1        perf    1        system  2021-11-25T10:11:23.601244  eowyn   NaN                    system  {'platform': {'system': 'Linux', 'node': 'eowy...
    2        perf    1     task_call  2021-11-25T10:11:23.870269  eowyn   NaN  omegaml.tasks.omega_ping  {'args': [], 'kwargs': {'__experiment': 'perf'...
    3        perf    1  task_success  2021-11-25T10:11:23.894004  eowyn   NaN  omegaml.tasks.omega_ping  {'result': {'message': 'ping return message', ...
    4        perf    1       profile  2021-11-25T10:11:23.900073  eowyn   0.0                profile_dt                         2021-11-25T10:11:23.532387
    5        perf    1       profile  2021-11-25T10:11:23.910524  eowyn   0.0               memory_load                                               27.5
    6        perf    1       profile  2021-11-25T10:11:23.918407  eowyn   0.0              memory_total                                        33542479872
    7        perf    1       profile  2021-11-25T10:11:23.926501  eowyn   0.0                  cpu_load                           [13.1, 11.2, 10.3, 17.3]
    8        perf    1       profile  2021-11-25T10:11:23.934526  eowyn   0.0                 cpu_count                                                  4
    9        perf    1       profile  2021-11-25T10:11:23.942705  eowyn   0.0                  cpu_freq                       [1.785, 2.642, 2.414, 1.846]
    10       perf    1       profile  2021-11-25T10:11:23.950802  eowyn   0.0                   cpu_avg                             [0.1425, 0.4225, 0.33]
    11       perf    1       profile  2021-11-25T10:11:23.958760  eowyn   0.0                  disk_use                                               97.2
    12       perf    1       profile  2021-11-25T10:11:23.966861  eowyn   0.0                disk_total                                       502468108288
    13       perf    1          stop  2021-11-25T10:11:23.974942  eowyn   NaN                       NaN                                                NaN
