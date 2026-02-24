Working with the cloud
======================

*Commercial Edition*

.. code:: bash

    $ om help cloud

    Usage:
      om cloud login [<userid>] [<apikey>] [options]
      om cloud config [show] [options]
      om cloud (add|update|remove) <kind> [--specs <specs>] [options]
      om cloud status [runtime|pods|nodes|storage] [options]
      om cloud log <pod> [--since <time>] [options]
      om cloud metrics [<metric_name>] [--since <time>] [--start <start>] [--end <end>] [--step <step>] [--plot] [options]

    Options:
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

    Description:
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


Logging into the cloud
----------------------

.. code:: bash

    $ om cloud login <USERID> <APIKEY>
    Config is in config.yml

The configuration is stored in :code:`config.yml` as follows:

.. code:: yaml

    OMEGA_APIKEY: ****
    OMEGA_RESTAPI_URL: https://hub.omegaml.io
    OMEGA_USERID: demo


Viewing the cloud status
------------------------

View important aspects of your omega-ml cloud environment.

Runtime
+++++++

.. code:: bash

    $ om cloud status runtime
    worker                         tasks  labels
    ---------------------------  -------  ---------------
    celery@worker-worker-omdemo        0  celery,default

Pods
++++

.. code:: bash

   $ om cloud status pods
    name                                             namespace    status    nodeName            nodeSelector
    -----------------------------------------------  -----------  --------  ------------------  ---------------------------
    worker-omdemo-worker-worker-omdemo-6f7c96f7c9    demo         Running   om-hub-demo-4c8gb1  omegaml.io/role=demo-worker

Nodes
+++++

.. code:: bash

    $ om cloud status nodes
    name                    status    role               cpu  memory    disk
    ----------------------  --------  ---------------  -----  --------  -------
    om-hub-demo-4c8gb1      running   demo-worker          4  7979Mi    47931Mi


Storage
+++++++

.. code:: bash

    $ om cloud status storage
    kind        size  status
    -------  -------  --------
    mongodb  2.44133  OK


Access cloud logs
-----------------

Access the log files of your cloud environment's pods. A pod is a named started
process. Query the name of the available pods using :code:`om cloud status pods`,
then access the log as follows:

.. code:: bash


