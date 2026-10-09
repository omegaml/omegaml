Parallel Execution
==================

The runtime.job.map() API let's you run a Jupyter notebook many times with
a different set of parameters. Essentially this works like Python's
multiprocessing Pool.map(), however runs Jupyter Notebooks across a node
of clusters.

The following snippet runs the 'mynb' notebook 10 times, in parallel. It
utilizes the omega|ml runtime cluster:

.. code:: python

    # run the 'mynb' notebook 10 times
    # -- each notebook gets one value of the range
    job = om.runtime.job('mynb')
    job.map(range(10))

Features:

* *Multitasking*: from a single base notebook, submit many tasks: :code:`job.map()`
* *Unattended processing*: the tasks are executed on the omegaml runtime cluster asynchronously, that
  is you can close Jupyter while the process is running
* *Automatic status tracking*: check the status of each task easily: :code:`job.status()`
* *Traceability*: see results of each task: open each tasks' results notebook in Jupyter or in om.jobs()
* *Restartable*: failed tasks can easily be restarted using :code:`job.restart()`
* *Debug in Jupyter*: open each task's notebook and run it manually
* *Keeping track*: Each task run is recorded in notebook metadata, including run status and errors

Concepts
--------

The basics are straight forward:

* main notebook: the notebook you want to run many times
* task notebook: a single copy of the main notebook, running a single part of your job. :code:`job.map()` creates
  as many task notebooks as specified automatically.
* results notebooks: the collection of all results. Every task notebook upon completion gets a result
  notebook.

In a nutshell, that's it. If you only want to use :code:`job.map()` that's all you need to know.

To make it work, we also need a few technical elements:

* job: the thing you call :code:`.map()` on, referencing a specific notebook on the omegaml runtime
* runner notebook: the notebook you use to start a job
* task group: the collection of all tasks from a single .map() call

And some more details to track the status:

* task_id: the id of the celery task (a single run of a task notebook)
* status: the celery status, PENDING, SUCCESS or ERROR
* run_status: the result of executing a task notebook, OK, ERROR


Motivating example:
-------------------

Assume we have a notebook like this:

.. code:: python

    # main.ipynb
    # -- get data for each group, run calculation, save data
    for group in range(100):
      data = om.datasets.get('mydata', group_id=group)
      result = calculate(data)
      om.datasets.put(result, 'results')

Now, we would like to run this notebook for many groups. Because calculate()
is long-running (say a few hours for every group, and there are a 1000 groups),
it is not a good idea to run a single notebook. If the processes crashes in between,
we have to start all over again and thus would lose time.

The better approach is to split the calculation into many groups, and run each
group in a separate notebook. Here is an example of one group:

.. code:: python

    # main.ipynb
    # -- specify the group
    job = {
       'group_id': 1
    }

    # -- get data for the group, run calculation, save data
    def calculation(group_id=None):
      data = om.datasets.get('mydata', group_id=group_id)
      result = calculate(data)
      om.datasets.put(result, 'results')

    calculation(group_id=job['group_id'])

Note that we did not change the notebook much. Essentially we created
a helper function, :code:`calculation()` that wraps our previous code,
and we added the :code:`job` variable to specify the :code:`group_id`.

With this setup, we could copy the same notebook for as many groups as we have,
and just run each notebook in turn. In essence, that's what :code:`job.map()`
does.

Consider the following example run:

.. code:: python

    # let's get a runtime reference to the "main" notebook
    In [16]: job = om.runtime.job('main')

    # now submit 10 tasks (=10 generated notebooks)
    # -- the input to each task notebook is one element of the iterable (here: range)
    In [17]: task_notebooks = job.map(range(10))
    generating task tasks/main/c05ecd89-0
    generating task tasks/main/c05ecd89-1
    generating task tasks/main/c05ecd89-2
    generating task tasks/main/c05ecd89-3
    generating task tasks/main/c05ecd89-4
    generating task tasks/main/c05ecd89-5
    generating task tasks/main/c05ecd89-6
    generating task tasks/main/c05ecd89-7
    generating task tasks/main/c05ecd89-8
    generating task tasks/main/c05ecd89-9
    started tasks/main/c05ecd89-0.ipynb => 16f2b598-f990-4be3-be16-ee6d1dbaa89a
    started tasks/main/c05ecd89-1.ipynb => 8b7b158b-eeb6-4bdb-9722-5a7c08054952
    started tasks/main/c05ecd89-2.ipynb => 06812d2c-fc75-4c59-a5d7-5ce5baef21c7
    started tasks/main/c05ecd89-3.ipynb => a7cec66e-44de-4c19-9723-54bc99508185
    started tasks/main/c05ecd89-4.ipynb => 79c27d1f-efed-40ca-9cbe-e94ab88eed15
    started tasks/main/c05ecd89-5.ipynb => 73260dc9-38da-4e81-a16b-875f18f8332f
    started tasks/main/c05ecd89-6.ipynb => aa1cac23-7bc1-45ce-973c-5beff897ff01
    started tasks/main/c05ecd89-7.ipynb => 50ca2c14-e3c7-42d1-98ad-68f1eb9979d9
    started tasks/main/c05ecd89-8.ipynb => 48e95505-0c7a-403f-8b0b-ed751a3ea345
    started tasks/main/c05ecd89-9.ipynb => abb2ed3f-d574-4c5b-8542-2858f1771dc0


:code:`.map()` created 10 new notebooks by copying our main notebook, setting
up the :code:`job` variable to contain the group_id for each one.

To be precise, :code:`.map()` does not know about group_id, and so we have to modify
the notebook slightly. Specifically, we need to get the group_id from the
parameter generated for each task notebook, taking the values from our
:code:`.map()` call:

.. code:: python

    # get the job, specify default value instead of None for testing
    # -- the 'param' value is taken from the .map() iterable
    job = globals().get('job', {'param': 9})

    def calculation(group_id=None):
        # same code as before
        ...

    calculation(group_id=job['param'])

With this, we can run :code:`.map()` again, as above. Let's check the status:

.. code:: python

    # let's check the status
    In [21]: job.status()
    Out[21]:
                              name                               task_id   status run_status
    0  tasks/main/cc1a3388-0.ipynb  5ed266bd-fb9f-42ef-b9c1-8729baeb4d59  PENDING    unknown
    1  tasks/main/cc1a3388-1.ipynb  e72af904-5b84-40b8-b8a9-8caaa7490157  PENDING    unknown
    2  tasks/main/cc1a3388-2.ipynb  b1d42852-c1d0-444d-b919-6c6f1ebe3842  PENDING    unknown
    3  tasks/main/cc1a3388-3.ipynb  7ce3e434-4f31-41e2-b7b3-ba1f86dc375c  PENDING    unknown
    4  tasks/main/cc1a3388-4.ipynb  df31754d-631b-45b6-b6fc-458ac6a4c520  PENDING    unknown
    5  tasks/main/cc1a3388-5.ipynb  9f456408-bc13-4bfb-89cf-e9436bfa4c37  PENDING    unknown
    6  tasks/main/cc1a3388-6.ipynb  794f2aed-6980-4d6a-bea6-94e0d992c7f3  PENDING    unknown
    7  tasks/main/cc1a3388-7.ipynb  64321f0b-0150-49a0-bfb1-cb43dd845e33  PENDING    unknown
    8  tasks/main/cc1a3388-8.ipynb  35c8fe3d-bb80-4c22-aa8a-78d44dd80390  PENDING    unknown
    9  tasks/main/cc1a3388-9.ipynb  47d576b1-9bbe-4021-abd0-39c8defa3290  PENDING    unknown

    # after a while the status is updated
    In [22]: job.status()
    Out[22]:
                              name                               task_id   status run_status
    0  tasks/main/cc1a3388-0.ipynb  5ed266bd-fb9f-42ef-b9c1-8729baeb4d59  SUCCESS         OK
    1  tasks/main/cc1a3388-1.ipynb  e72af904-5b84-40b8-b8a9-8caaa7490157  SUCCESS         OK
    2  tasks/main/cc1a3388-2.ipynb  b1d42852-c1d0-444d-b919-6c6f1ebe3842  SUCCESS         OK
    3  tasks/main/cc1a3388-3.ipynb  7ce3e434-4f31-41e2-b7b3-ba1f86dc375c  SUCCESS         OK
    4  tasks/main/cc1a3388-4.ipynb  df31754d-631b-45b6-b6fc-458ac6a4c520  SUCCESS         OK
    5  tasks/main/cc1a3388-5.ipynb  9f456408-bc13-4bfb-89cf-e9436bfa4c37  SUCCESS         OK
    6  tasks/main/cc1a3388-6.ipynb  794f2aed-6980-4d6a-bea6-94e0d992c7f3  SUCCESS         OK
    7  tasks/main/cc1a3388-7.ipynb  64321f0b-0150-49a0-bfb1-cb43dd845e33  SUCCESS         OK
    8  tasks/main/cc1a3388-8.ipynb  35c8fe3d-bb80-4c22-aa8a-78d44dd80390  SUCCESS         OK
    9  tasks/main/cc1a3388-9.ipynb  47d576b1-9bbe-4021-abd0-39c8defa3290  SUCCESS         OK

Great! All tasks have run to completion. We can see each task's results by checking
the results folder in Jupyter, as each task has created a results notebook:

.. code:: python

    In [34]: om.jobs.list('results/tasks/main/cc1a3388*')
    Out[34]:
    ['results/tasks/main/cc1a3388-0.ipynb_2020-10-22 11:34:30.751235.ipynb',
     'results/tasks/main/cc1a3388-1.ipynb_2020-10-22 11:34:30.857055.ipynb',
     'results/tasks/main/cc1a3388-2.ipynb_2020-10-22 11:34:30.937543.ipynb',
     'results/tasks/main/cc1a3388-3.ipynb_2020-10-22 11:34:30.997867.ipynb',
     'results/tasks/main/cc1a3388-4.ipynb_2020-10-22 11:34:31.087035.ipynb',
     'results/tasks/main/cc1a3388-5.ipynb_2020-10-22 11:48:13.000348.ipynb',
     'results/tasks/main/cc1a3388-6.ipynb_2020-10-22 11:34:31.296300.ipynb',
     'results/tasks/main/cc1a3388-7.ipynb_2020-10-22 11:34:31.349900.ipynb',
     'results/tasks/main/cc1a3388-8.ipynb_2020-10-22 11:34:42.562762.ipynb',
     'results/tasks/main/cc1a3388-9.ipynb_2020-10-22 11:34:42.562477.ipynb']

Dealing with errors
-------------------

What if a task has produced an error?

We can use the tasks metadata to see the result of running the notebook:

.. code:: python

    # lookup the the metadata from the job.status() that has an error
    meta = om.jobs.metadata('tasks/main/cc1a3388-9')
    print(meta.attributes['job_runs'][-1])
    {'job': {'param': 0,
      'job_id': 0,
      'task_group': '2e3368ad',
      'task_name': 'tasks/main/2e3368ad-0',
      'status': 'finished',
      'task_id': 'bceccd43-099d-4ac4-ae89-3e8d8953ea6e'},
     'job_results': ['results/tasks/main/2e3368ad-0.ipynb_2020-10-21 01:37:52.358832.ipynb'],
     'job_runs': [{'status': 'OK',
       'ts': datetime.datetime(2020, 10, 21, 1, 37, 52, 358000),
       'message': '',
       'results': 'results/tasks/main/2e3368ad-0.ipynb_2020-10-21 01:37:52.358832.ipynb'}],
     'state': 'SUCCESS',
     'task_id': 'bceccd43-099d-4ac4-ae89-3e8d8953ea6e'}


What if a task did not produce a result?

For demo purpose, let's delete one of  the result notebooks.
Then we can call :code:`job.restart()`. This  will look for task notebooks
that don't have a result yet, and simply start it again. All the other tasks
that already have a result are not run again.

.. code:: python

    # if one of them is missing results, we can simply restart
    # -- for demo purpose, I just deleted the ...-5 task's result notebook
    # -- .restart() will look for a result notebook, if it can't find, will submit
    # -- the tasks notebook again
    In [23]: job.restart()
    tasks/main/cc1a3388-0.ipynb has already got results
    tasks/main/cc1a3388-1.ipynb has already got results
    tasks/main/cc1a3388-2.ipynb has already got results
    tasks/main/cc1a3388-3.ipynb has already got results
    tasks/main/cc1a3388-4.ipynb has already got results
    started tasks/main/cc1a3388-5.ipynb => 302a31dd-525d-4e36-b34d-bbb00a6ec46a
    tasks/main/cc1a3388-6.ipynb has already got results
    tasks/main/cc1a3388-7.ipynb has already got results
    tasks/main/cc1a3388-8.ipynb has already got results
    tasks/main/cc1a3388-9.ipynb has already got results

We can also force a re-run of tasks:

.. code:: python

    # the same as removing all the results notebooks first
    om.restart(reset=True)


Running tasks on specific nodes
--------------------------------

How can we choose a specific node to run this on?

Say we want to run on the GPU node:

.. code:: python

    job.map(range(10), require='gpu')

We can also run the process twice, say:

1. on a smaller, inexpensive node for testing
2. on a high performance node for the actual run

.. code:: python

    # run testing
    job.map(range(10), require='default')

    # if tests are successful, run the real deal
    job.map(range(10000), require='gpu')


See all previous runs
----------------------

To get a list of all the tasks that were created for a notebook:

.. code:: python

    In [54]: job = om.runtime.job('main')
             job.list()
    Out[54]:
    ['tasks/main/0ef102e2-0.ipynb',
     'tasks/main/0ef102e2-1.ipynb',
     'tasks/main/0ef102e2-2.ipynb',
    ...]

To get the status of all previous runs:

.. code:: python

    # this can take a while if there were many previous .map() calls!
    In [55]: job.status(task_group='*')
                                name                               task_id   status run_status
    0    tasks/main/0ef102e2-0.ipynb  e937b1a2-a237-4208-878a-a6cf07d5c973  PENDING         OK
    1    tasks/main/0ef102e2-1.ipynb  cfd9ee22-3637-4b77-8d5b-630de5b368c9  PENDING         OK
    2    tasks/main/0ef102e2-2.ipynb  d0e961bf-2493-45f2-baf1-d1e53520aaae  PENDING         OK
    3    tasks/main/0ef102e2-3.ipynb  cdf061e5-7d98-4990-a131-b6e19387efed  PENDING         OK
    4    tasks/main/0ef102e2-4.ipynb  a269eed8-48a6-4125-9987-67ba43c83b17  PENDING         OK

