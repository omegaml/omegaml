Using the command-line interface
================================

Open your command line shell to run commands:

.. code:: bash

   $ om
   Usage: om <command> [<action>] [<args>...] [options]
       om (models|datasets|scripts|jobs) [<args>...] [--replace] [--csv...] [options]
       om runtime [<args>...] [--async] [--result] [--param] [options]
       om cloud [<args>...] [options]
       om shell [<args>...] [options]
       om help [<command>]


Similar in structure to the Python API the command-line interface provides
access to the

* storages - access datasets, models, scripts, jobs
* runtime - interact with the omega-ml runtime
* cloud - managed service configuration and access
* shell - the Python shell with omegaml initialized

See the respective section in this guide to learn more about the various
commands.


Getting help
------------

The cli provides built-in help

.. code:: bash

    $ om help
    Usage: om <command> [<action>] [<args>...] [options]
           om (models|datasets|scripts|jobs) [<args>...] [--replace] [--csv...] [options]
           om runtime [<args>...] [--async] [--result] [--param] [options]
           om cloud [<args>...] [options]
           om shell [<args>...] [options]
           om help [<command>]

    Usage of datasets
      om datasets list [<pattern>] [--raw] [-E|--regexp] [options]
      om datasets put <path> <name> [--replace] [--csv=<param=value>]... [options]
      om datasets get <name> <path> [--csv <param>=<value>]... [options]
      om datasets drop <name> [--force] [options]
      om datasets metadata <name> [options]

    Usage of models
      om models list [<pattern>] [--raw] [-E|--regexp] [options]
      om models put <module.callable> <name>
      om models drop <name>
      om models metadata <name>

    Usage of runtime
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

    Usage of scripts
        om scripts list [<pattern>] [--raw] [--hidden] [-E|--regexp] [options]
        om scripts put <path> <name> [options]
        om scripts get <name>
        om scripts drop <name> [options]
        om scripts metadata <name>

    Usage of jobs
      om jobs list [<pattern>] [--raw] [options]
      om jobs put <path> <name> [options]
      om jobs get <name> <path> [options]
      om jobs drop <name>
      om jobs metadata <name> [options]
      om jobs schedule <name> [show|delete|<interval>] [options]
      om jobs status <name>

    Usage of cloud
      om cloud login [<userid>] [<apikey>] [options]
      om cloud config [show] [options]
      om cloud (add|update|remove) <kind> [--specs <specs>] [options]
      om cloud status [runtime|pods|nodes|storage] [options]
      om cloud log <pod> [--since <time>] [options]
      om cloud metrics [<metric_name>] [--since <time>] [--start <start>] [--end <end>] [--step <step>] [--plot] [options]

    Usage of shell
        om shell [<command>] [options]

    Options:
      -h, --help         Show this screen
      --version          Show version.
      --loglevel=LEVEL   INFO,ERROR,DEBUG [default: INFO]
      --copyright        Show copyright
      --config=CONFIG    configuration file
      --bucket=BUCKET    the bucket to use
      --local-runtime    use local runtime
      -q, --noinput      don't ask for user input, assume yes
      -E                 treat patterns as regular expressions

    Options for datasets
      --raw   return metadata

    Options for runtime
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

    Options for cloud
      --userid=USERID   the userid at hub.omegaml.io (see account profile)
      --apikey=APIKEY   the apikey at hub.omegaml.io (see account profile)
      --apiurl=URL      the cloud URL [default: https://hub.omegaml.io]
      --count=NUMBER    how many instances to set up [default: 1]
      --node-type=TYPE  the type of node [default: small]
      --specs=SPECS     the service specifications as "key=value[,...]"
      --since=TIME      recent log time, defaults to 5m (5 minutes)
      --start=DATETIME  start datetime of range query
      --end=DATETIME    end datetime of range query
      --step=UNIT       step in seconds or duration unit (s=seconds, m=minutes)
      --plot            if specified use plotext library to plot (preliminary)

    Options for scripts
        --hidden   list hidden entries

    Options for jobs
      --cron <spec>       the cron spec, use https://crontab.guru/
      --weekday <wday>    a day number 0-6 (0=Sunday)
      --monthday <mday>   a day of the month 1-31
      --month <month>     a month number 1-12
      --at <hh:mm>        the time (same as --hour hh --minute mm)
      --hour <hour>       the hour 0-23
      --minute <minute>   the minute 0-59
      --next <n>          show next n triggers according to interval

    Working with datasets
         For csv files, put and get accept the --csv option multiple times.
         The <param>=<value> pairs will be used as kwargs to pd.read_csv (on put)
         and df.to_csv methods (on get)

    Working with models
        Work with models

    Working with runtime
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

    Working with cloud
      om cloud is available for the omega-ml managed service at https://hub.omegaml.io

      Logging in
      ----------

      $ om cloud login <userid> <apikey>

      Showing the configuration
      -------------------------

      $ om cloud config

      Building a cluster
      ------------------

      Set up a cluster

      $ om cloud add nodepool --specs "node-type=<node-type>,role=worker,size=1"
      $ om cloud add runtime --specs "role=worker,label=worker,size=1"

      Switch nodes on and off

      $ om cloud update worker --specs "node-name=<name>,scale=0" # off
      $ om cloud update worker --specs "node-name=<name>,scale=1" # on

      Using Metrics
      -------------

      The following metrics are available

      * node-cpu-usage      node cpu usage in percent
      * node-memory-usage   node memory usage in percent
      * node-disk-uage      node disk usage in percent
      * pod-cpu-usage       pod cpu usage in percent
      * pod-memory-usage    pod memory usage in bytes

      Get the specific metrics as follows, e.g.

      $ om cloud metrics node-cpu-usage
      $ om cloud metrics pod-cpu-usage --since 30m
      $ om cloud metrics pod-memory-usage --start 20dec2020T0100 --end20dec2020T0800

    Working with scripts
        Work with scripts

    Working with jobs
        Specify the schedule either as

        * a natural language-like text, with any time components separated
          by comma

          om jobs schedule myjob "every 5 minutes, on fridays, in april"
          om jobs schedule myjob "at 6:00, on fridays"
          om jobs schedule myjob "at 6:00/10:00, on fridays"
          om jobs schedule myjob "every 2nd hour, every 15 minutes, weekdays"



    Working with shell
        Without a command will start an IPython shell with omega-ml ready to use

        $ om shell
        [] om.runtime.ping()
        => { ... }

        By passing a command, run arbitrary Python code

        $ om shell "om.runtime.ping()"


