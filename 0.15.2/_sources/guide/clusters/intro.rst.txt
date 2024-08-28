What is the runtime?
====================

.. contents::

.. _Celery: https://docs.celeryproject.org/en/stable/

The omega-ml runtime provides distributed and highly scalable execution of
all of the omega-ml functionality. It is a distributed programming and
deployment environment based on the widely used  `Celery`_ library.

Key functionality includes

* distributed model training, scoring and prediction
* tracking of experiment metrics across a distributed set of workers
* straight-forward logging from any work load, including models, Python scripts
  and notebooks
* parallel, map-reduce and sequenced execution of data and model pipelines
* easily switch workers without changing your code (e.g. local, remote cpu,
  remote gpu, any cloud)

For Jupyter notebooks, the runtime provides additional functionality:

* easy scheduling of notebooks
* transparent results logging and status tracking
* parallel execution using :code:`Multiprocessing.map()` semantics,
  including automated restarts of failed partial tasks

Concepts
--------

* **workers**  - a worker is a compute server that waits to receive commands,
  every worker responds to one or more *labels*, where a label specifies a
  worker's capabilities (e.g. whether it provides cpu or gpu resources)
* **tasks** - tasks describe the specific action to execute, e.g. *fit a model*,
  *predict from a model*, *run a script*, *run a notebook*
* **object references** - references link tasks to models, datasets and other
  objects accessible via omega-ml's Metadata

For example, to fit a model, we can use the omega-ml runtime as follows. This
sends the task *fit the model mymodel using datasets data-X, data-Y* to the
default runtime worker, waiting for the task to complete.

.. code::

    # mymodel is a fitted model, newdata the name of a dataset
    result = om.runtime.model('mymodel').fit('data-X', 'data-Y')
    result.get()

Running tasks
-------------

The runtime provides built-in tasks for models, jobs (notebooks) and scripts.
In general the syntax follows the pattern *om.runtime.<kind>(name).<action>*.
Every task returns as :code:`AsyncResult` result object, which is a reference
to the result of the task execution on a remote worker described in
:ref:`Asynchronous execution`. To get the actual result, call :code:`result.get()`

.. code:: python

    result = om.runtime.model('mymodel').fit(*args, **kwargs)
    result = om.runtime.script('myscript').run(*args, **kwargs)
    result = om.runtime.job('mynotebook').run(*args, **kwargs)

Submitting tasks to specific workers
------------------------------------

Every worker is assigned one or more *labels*. A label is just an arbitrary
name but it should signify the worker's capabilities, e.g. *cpu* or *gpu*. The
default label is :code:`default`.

The list of available workers and their labels can be retrieved by running

.. code:: python

    om.runtime.labels()
    =>
    {'celery@eowyn': ['default']}

Tasks can be submitted to a specific worker by specifying :code:`.require(label)`
just before the actual call:

.. code:: python

    om.runtime.require('gpu').model('mymodel').fit(*args, **kwargs)


Asynchronous execution
----------------------

All runtime tasks are run asynchronously. This means that any task submitted
to a runtime worker is put into a waiting queue until a worker can respond to
it. The immediate result returned by a call to the runtime is a reference
to the task, also known as a *promise* i.e. a reference to a future result.

.. code:: python

    result = om.runtime.model('mymodel').predict('new-X')
    type(result)
    => <AsyncResult: eda3b2f9-f675-4690-8303-2a944783147c>

We can check the execution state by looking at the :code:`result.status`.
The states are PENDING, STARTED, SUCCESS or FAILURE.

.. code:: python

    result.status
    =>
    PENDING

To wait for the task to complete and get back the actual result call :code:`result.get()`:

.. code:: python

    result.get()
    =>
    [5, 10, 11, 15]


Parallel and pipelined task execution
-------------------------------------

The runtime is built for horizontal scalability, which means it can process
many tasks in parallel. One easy way to submit tasks in parallel is to call
the runtime in a loop. One caveat is that we need to keep track of every
result's status.

.. code:: python

        results = []
        for i in range(5):
            result = om.runtime.job(f'myjob{i}').run(i)
            results.append(result)

        while not done:
            done = all(r.status == 'SUCCESS' for r in results)

        print(results)

omega-ml provides easier semantics for the three typical ways in which
to run many tasks:

* sequence - run tasks in a given sequence
* parallel - run tasks in parallel, independent of sequence
* mapreduce - run many tasks in parallel, combine results in a last step

Running many tasks in sequence
++++++++++++++++++++++++++++++

:code:`sequence()` runs tasks in sequence, forwarding results from the
previous task to the next.

.. code:: python

    with om.runtime.sequence() as crt:
        for i in range(5):
            om.runtime.job(f'myjob{i}').run(i)
        result = crt.run()
    result.getall()
    =>
    ['<Metadata: Metadata(name=results/myjob_2021-11-25 14:02:14.690974.ipynb,bucket=omegaml,prefix=jobs/,kind=script.ipynb,created=2021-11-25 14:02:15.814244)>',
     '<Metadata: Metadata(name=results/myjob_2021-11-25 14:02:12.101315.ipynb,bucket=omegaml,prefix=jobs/,kind=script.ipynb,created=2021-11-25 14:02:13.185000)>',
     '<Metadata: Metadata(name=results/myjob_2021-11-25 14:02:13.247192.ipynb,bucket=omegaml,prefix=jobs/,kind=script.ipynb,created=2021-11-25 14:02:14.605521)>',
     '<Metadata: Metadata(name=results/myjob_2021-11-25 14:02:15.899301.ipynb,bucket=omegaml,prefix=jobs/,kind=script.ipynb,created=2021-11-25 14:02:17.157619)>',
     '<Metadata: Metadata(name=results/myjob_2021-11-25 14:02:10.690568.ipynb,bucket=omegaml,prefix=jobs/,kind=script.ipynb,created=2021-11-25 14:02:12.037948)>']


Running many tasks in parallel
++++++++++++++++++++++++++++++

:code:`parallel()` runs many tasks in parallel.

.. code:: python

    with om.runtime.parallel() as crt:
        for i in range(5):
            om.runtime.job(f'myjob{i}').run(i)
        result = crt.run()
    result.getall()
    =>
    ['<Metadata: Metadata(name=results/myjob_2021-11-25 14:02:14.690974.ipynb,bucket=omegaml,prefix=jobs/,kind=script.ipynb,created=2021-11-25 14:02:15.814244)>',
     '<Metadata: Metadata(name=results/myjob_2021-11-25 14:02:12.101315.ipynb,bucket=omegaml,prefix=jobs/,kind=script.ipynb,created=2021-11-25 14:02:13.185000)>',
     '<Metadata: Metadata(name=results/myjob_2021-11-25 14:02:13.247192.ipynb,bucket=omegaml,prefix=jobs/,kind=script.ipynb,created=2021-11-25 14:02:14.605521)>',
     '<Metadata: Metadata(name=results/myjob_2021-11-25 14:02:15.899301.ipynb,bucket=omegaml,prefix=jobs/,kind=script.ipynb,created=2021-11-25 14:02:17.157619)>',
     '<Metadata: Metadata(name=results/myjob_2021-11-25 14:02:10.690568.ipynb,bucket=omegaml,prefix=jobs/,kind=script.ipynb,created=2021-11-25 14:02:12.037948)>']


Running many tasks to combine results (mapreduce)
+++++++++++++++++++++++++++++++++++++++++++++++++

:code:`mapreduce` runs tasks in parallel, except for the last one. The last
task will wait for all parallel jobs to be completed and then runs to combine the
previous results.

.. code:: python

    with om.runtime.mapreduce() as crt:
        for i in range(5):
            om.runtime.job(f'myjob{i}').run(i)
        result = crt.run()
    result.collect()
    =>
    {<AsyncResult: 33e7baf0-1905-4ff4-aecb-8d6ee43fd9b1>,
     <GroupResult: a42f9d7b-3c36-456c-9f13-23acda3c1ae0 [b6f67c16-3a98-474c-b97a-544b7bb20291,
      fa95a436-fc70-46ad-97ee-a31a9a3a5720, 78e060e8-59d9-4244-a2db-10f18a49a0c0,
      541761d9-6c56-4a9e-a815-3959b01609ae]>}

