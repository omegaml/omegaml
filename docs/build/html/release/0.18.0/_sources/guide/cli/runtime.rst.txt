Working with the runtime
========================

The runtime is the collection of omegaml workers that wait for models, jobs
or scripts to be run. The runtime works fully asynchronously by receiving,
processing and returning messages.

.. note::

    Technically the omegaml runtime is a Celery cluster made up of 1 to
    many worker nodes. Every worker node runs a pool of 1 to many
    Celery processes. Think of a worker as a pre-started and pre-configured
    Python environment waiting for work.


.. code:: bash

    $ om help runtime

    Usage:
      om runtime model <name> <model-action> [<X>] [<Y>] [--result=<output-name>] [--param=<kw=value>]... [--async] [options]
      om runtime script <name> [<script-action>] [<kw=value>...] [--async] [options]
      om runtime job <name> [<job-action>] [<args...>] [--async] [options]
      om runtime result <taskid> [options]
      om runtime ping [options]
      om runtime env <action> [<package>] [--file <requirements.txt>] [--every] [options]
      om runtime log [-f] [options]
      om runtime status [workers|labels|stats] [options]
      om runtime restart app <name> [options]
      om runtime [control|inspect|celery] [<celery-command>...] [--worker=<worker>] [--queue=<queue>] [--celery-help] [--flags <celery-flags>...] [options]

    Options:
      --async           don't wait for results, will print taskid
      -f                tail log
      --require=VALUE   worker label
      --flags=VALUE     celery flags, list as "--flag VALUE"
      --worker=VALUE    celery worker
      --queue=VALUE     celery queue
      --celery-help     show celery help
      --file=VALUE      path/to/requirements.txt
      --local           if specified the task will run locally. Use this for testing
      --every           if specified runs task on all workers

    Description:
      model, job and script commands
      ------------------------------

      <model-action> can be any valid model action like fit, predict, score,
      transform, decision_function etc.

      <script-action> defaults to run
      <job-action> defaults to run

      Examples:
        om runtime model <name> fit <X> <Y>
        om runtime model <name> predict <X>
        om runtime job <name>
        om runtime script <name>
        om runtime script <name> run myparam="value"

      running asynchronously
      ----------------------

      model, job, script commands accept the --async paramter. This will submit
      the a task and return the task id. To wait for and get the result run use
      the result command

      Examples:
            om runtime model <name> fit <X> <Y> --async
            => <task id>
            om runtime result <task id>
            => result of the task

      restart app
      -----------

      This will restart the app on omegaml apphub. Requires a login to omegaml cloud.


      status
      ------

      Prints workers, labels, list of active tasks per worker, count of tasks

      Examples:
        om runtime status             # defaults to workers
        om runtime status workers
        om runtime status labels
        om runtime status stats

      celery commands
      ---------------

      This is the same as calling celery -A omegaml.celeryapp <commands>. Command
      commands include:

      inspect active         show currently running tasks
      inspect active_queues  show active queues for each worker
      inspect stats          show stats of each worker, including pool size (processes)
      inspect ping           confirm that worker is connected

      control pool_shrink N  shrink worker pool by N, specify 99 to remove all
      control pool_grow N    grow worker poool by N
      control shutdown       stop and restart the worker

      Examples:
            om runtime celery inspect active
            om runtime celery control pool_grow N


      env commands
      ------------

      This talks to an omegaml worker's pip environment

      a) install a specific package

         env install <package>    install the specified package, use name==version pip syntax for specific versions
         env uninstall <package>  uninstall the specified package

         <package> is in pip install syntax, e.g.

         env install "six==1.0.0"
         env install "git+https://github.com/user/repo.git"

      b) use a requirements file

         env install --file requirements.txt
         env uninstall --file requirements.txt

      c) list currently installed packages

         env freeze
         env list

      d) install on all or a specific worker

         env install --require gpu package
         env install --every package

         By default the installation runs on the default worker only. If there are multiple nodes where you
         want to install the package(s) worker nodes, be sure to specify --every

      Examples:
            om runtime env install pandas
            om runtime env uninstall pandas
            om runtime env install --file requirements.txt
            om runtime env install --file gpu-requirements.txt --require gpu
            om runtime env install --file requirements.txt --every


Inspect runtime status
----------------------

.. code:: bash

    $ om runtime status
    $ om runtime status labels
    $ om runtime status stats


Monitor live events
-------------------

.. _Celery events: https://docs.celeryproject.org/en/stable/userguide/monitoring.html#celery-events-curses-monitor

Launch the `Celery Events`_ monitor as follows

.. code:: bash

    $ om runtime celery events
    $ om runtime celery flower


See active work items
---------------------

.. code:: bash

    $ om runtime inspect active
      -> celery@worker-worker-omdemo: OK
          - empty -


Ping the worker
---------------

.. code:: bash

    $ om runtime ping
    {'message': 'ping return message', 'time': '2021-02-22T13:27:49.723657', 'args': (), 'kwargs': {}, 'worker': 'celery@worker-worker-omdemo'}


Restart the worker
------------------

.. code:: bash

    $ om runtime control shutdown

Install new packages
--------------------

.. code:: bash

    $ om runtime env install "git+https://github.com/omegaml/omegaml.git@enable-long-dataset-names" --require default

Note it is best to restart the worker to make sure the newest package versions
are loaded. For example to upgrade omegaml itself:

.. code:: bash

    $ om runtime env install omegaml
    $ om runtime control shutdown

To upgrade a package on every worker, specify :code:`--every`. This will send the installation
command to all workers.

.. code:: bash

    $ om runtime env install omegaml --every

