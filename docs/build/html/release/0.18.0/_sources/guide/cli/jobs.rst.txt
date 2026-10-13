Working with notebooks
======================

.. note::

   Jupyter notebooks stored in omegaml are called jobs because the main purpose
   of storing notebooks in omegaml is to easily transform notebooks into
   remotely executed programs, optionally scheduled to run at a particular time
   (e.g. nightly, daily, every fortnight etc.)

.. code:: bash

    $ om help jobs
    Usage:
      om jobs list [<pattern>] [--raw] [options]
      om jobs put <path> <name> [options]
      om jobs get <name> <path> [options]
      om jobs drop <name>
      om jobs metadata <name> [options]
      om jobs schedule <name> [show|delete|<interval>] [options]
      om jobs status <name>

    Options:
      --cron <spec>       the cron spec, use https://crontab.guru/
      --weekday <wday>    a day number 0-6 (0=Sunday)
      --monthday <mday>   a day of the month 1-31
      --month <month>     a month number 1-12
      --at <hh:mm>        the time (same as --hour hh --minute mm)
      --hour <hour>       the hour 0-23
      --minute <minute>   the minute 0-59
      --next <n>          show next n triggers according to interval

    Description:
        Specify the schedule either as

        * a natural language-like text, with any time components separated
          by comma

          om jobs schedule myjob "every 5 minutes, on fridays, in april"
          om jobs schedule myjob "at 6:00, on fridays"
          om jobs schedule myjob "at 6:00/10:00, on fridays"
          om jobs schedule myjob "every 2nd hour, every 15 minutes, weekdays"


Storing a notebook
------------------

A notebook in the :code:`.ipynb` format may be stored as follows:

.. code:: bash

    $ om jobs put /path/to/mynotebook.ipynb mynotebook


Retrieve a notebook
-------------------

Retrieve a notebook to a local file as follows:

.. code:: bash

    $ om jobs get mynotebook /path/to/mynotebook.ipynb


Running notebooks
-----------------

Run notebooks as jobs on the omega-ml runtime:

.. code:: bash

    $ om runtime job mynotebook
    <Metadata: Metadata(name=results/main_2021-02-22 12:52:45.665179.ipynb,bucket=omegaml,prefix=jobs/,kind=script.ipynb,created=2021-02-22 12:52:47.725302)>


This runs the notebook and stores the results in the :code:`jobs/results` folder.
The execution and its result status are also recorded in the job's Metadata entry:

.. code:: json

  $ om jobs metadata mynotebook | jq
  {
      "name": "mynotebook.ipynb",
      "bucket": "omegaml",
      "prefix": "jobs/",
      "kind": "script.ipynb",
      "kind_meta": {},
      "attributes": {
        "job_results": [
          "results/main_2021-02-22 12:52:45.665179.ipynb"
        ],
        "job_runs": [
          {
            "status": "OK",
            "ts": {
              "$date": 1613998365665
            },
            "message": "",
            "results": "results/main_2021-02-22 12:52:45.665179.ipynb"
          }
        ],
        "state": "SUCCESS",
        "task_id": "881100ed-161c-4c18-ad8e-cc7db9102788"
      },
    }


Scheduling notebooks
--------------------

.. _cron schedule: http://www.cronmaker.com/?0

Notebooks may be scheduled to run at particular times using a natural language-like
specification in the format :code:`[timepart, ...]` where timepart is either

* an interval like "every 5 minutes"
* a time like "at 6:00"
* a day specifier like "weekdays" or "on fridays"
* a month specifier like "in april"

.. code:: bash

    $ om jobs schedule myjob "every 5 minutes, on fridays, in april"
    $ om jobs schedule myjob "at 6:00, on fridays"
    $ om jobs schedule myjob "at 6:00/10:00, on fridays"
    $ om jobs schedule myjob "every 2nd hour, every 15 minutes, weekdays"

The interval may also be specified as a `cron schedule`_:

.. code:: bash

    $ om jobs schedule myjob --cron "0 0 12 ? * MON *"

The interval may also be specified using several options

.. code:: bash

    $ om jobs schedule myjob --hour 23 --weekday 6

The results of the scheduled jobs will be stored the same way as if the job
is run directly.

Checking the status of notebook runs
------------------------------------

The status of a notebook run can be checked as follows:

.. code:: bash

    $ om jobs status main
    Runs:
      2021-02-04 20:19:08.445000 OK
      2021-02-04 20:19:10.398000 OK
      2021-02-22 12:52:45.665000 OK
    Next scheduled runs:


