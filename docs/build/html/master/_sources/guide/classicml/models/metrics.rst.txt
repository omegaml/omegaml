Capturing model metrics
=======================

.. contents::

omega-ml provides experiment and model tracking for all models using its
built-in metrics store.

Running an experiment
---------------------

Collecting metrics as part of an experiment is straight forward:

.. code:: python

    lr = LogisticRegression()
    X, Y = ...

    with om.runtime.experiment('myexp') as exp:
        lr.fit(X, Y)
        score = lr.score(X, Y)
        exp.log_metric('accuracy', score)
        exp.log_param('penalty', 'L2')
        exp.log_artifact(lr, 'mymodel')

We can get back the data collected in an experiment using :code:`exp.data()`,
as a DataFrame:

.. code:: python

        In [1]: exp.data()
        Out[2]:
              experiment  run     event                          dt   node  step       key                                              value
        0      myexp    1     start  2021-11-22T15:49:51.893920  eowyn   NaN       NaN                                                NaN
        1      myexp    1    system  2021-11-22T15:49:51.927902  eowyn   NaN    system  {'platform': {'system': 'Linux', 'node': 'eowy...
        2      myexp    1    metric  2021-11-22T15:49:51.938601  eowyn   NaN  accuracy                                                  1
        3      myexp    1     param  2021-11-22T15:49:51.950340  eowyn   NaN  penaltiy                                                 L2
        4      myexp    1  artifact  2021-11-22T15:49:51.984030  eowyn   NaN   mymodel  {'name': 'mymodel', 'data': 'experiments/.arte...
        5      myexp    1      stop  2021-11-22T15:49:51.994113  eowyn   NaN       NaN                                                NaN

Note the :code:`run` column records the number of times the above :code:`with`
block has been run. If you run it again, there is a second set of metrics. We can
get back all the runs by filtering as :code:`exp.data(run='all')`, or a specific set
of runs by giving a list or a tuple :code:`exp.data(run=(1,3))`. Additional
filters are available for the :code:`event, node, step, key` fields

.. code:: python

    In [3]: exp.data(run='all', key='accuracy')
    Out[4]:
      experiment  run  step   event       key  value                          dt   node
    0      myexp    1  None  metric  accuracy      1  2021-11-22T15:49:51.938601  eowyn
    1      myexp    2  None  metric  accuracy      1  2021-11-22T16:02:08.579077  eowyn
    2      myexp    3  None  metric  accuracy      1  2021-11-22T16:02:13.048647  eowyn


Tracking experiments with multiple steps
----------------------------------------

To run an experiment that uses a series of parameters or a k-fold of input data
such as in cross-validation, we can track each step separately. In this case there
the data will be recorded for one run (e.g. :code:`run=1`) and many steps.

.. code:: python

    shuffle = ShuffleSplit(n_splits=5)
    with om.runtime.experiment('myexp') as exp:
        for step, split in enumerate(shuffle.split(X))
            Xs, Ys = X[split[0]], Y[split[1]]
            lr.fit(Xs, Ys)
            score = lr.score(X, Y, step=step)
            exp.log_metric('accuracy', score, step=step)
            exp.log_param('penalty', 'L2', step=step)
            exp.log_artifact(lr, 'mymodel', step=step)


If the ML framework provides model callbacks, such as Tensorflow, the model can
be fit using :code:`exp.tensorflow_callback()`. In this case, the model itself
will provide model metrics via the callback:

.. code:: python

    model = Sequential()
    ...
    model.compile(metrics=['accuracy'])
    with om.runtime.experiment('myexp') as exp:
        model.fit(X, Y,
                  callbacks=[exp.tensorflow_callback()])


Tracking model execution at runtime
-----------------------------------

Since experiments are a feature of the runtime, we can store a model
and link it to an experiment. In this case the runtime will create an
experiment context prior to performing the requested model action.

.. code:: python

    lr = LogisticRegression()
    om.models.put(lr, 'mymodel', attributes={
        'tracking': {
            'default': 'myexp',
        }})
    om.runtime.model('mymodel').score(X, Y)

Thus the runtime worker will run the following code equivalent. This is
true for all calls of the runtime (programmatic, cli or REST API).

.. code:: python

    # run time worker, in response to om.runtime.score('mymodel', X, Y)
    def omega_score(X, Y):
        model = om.models.get('mymodel')
        meta = om.models.metadata('mymodel')
        exp_name = meta.attributes['tracking']['default']
        with om.runtime.experiment(exp_name) as exp:
            exp.log_event('task_call', 'mymodel')
            result = model.score(X, Y)
            exp.log_metric('score', result)
            exp.log_artifcat(meta, 'related')
            exp.log_event('task_success', 'mymodel')


Customizing tracking behavior
-----------------------------

Tracking behavior can be adjusted by using a different tracking provider,
e.g. the :code:`SimpleTrackingProvider` logs model metrics, while the
:code:`OmegaProfilingTracker` also logs system resource usage like
CPU and RAM while running the experiment. Write your own tracking providers
to forward metrics to a third-party metrics store, or to provide custom
callbacks to your machine learning framework.

The specific tracking provider used is specified as the :code:`provider=`
argument when creating the experiment. For example, the 'profiling' provider
will track system metrics during execution:

.. code::

    In [1]: with om.runtime.experiment('myexp2',
                                        provider='profiling') as exp:
                 ...
    Out[2]: exp.data()
           experiment  run     event                          dt   node  step           key                                              value
        0      myexp2    1     start  2021-11-22T16:53:28.534211  eowyn   NaN           NaN                                                NaN
        1      myexp2    1    system  2021-11-22T16:53:28.579121  eowyn   NaN        system  {'platform': {'system': 'Linux', 'node': 'eowy...
        2      myexp2    1    metric  2021-11-22T16:53:28.592081  eowyn   NaN      accuracy                                                  1
        3      myexp2    1     param  2021-11-22T16:53:28.600690  eowyn   NaN      penaltiy                                                 L2
        4      myexp2    1  artifact  2021-11-22T16:53:28.627970  eowyn   NaN       mymodel  {'name': 'mymodel', 'data': 'experiments/.arte...
        5      myexp2    1   profile  2021-11-22T16:53:28.635717  eowyn   0.0    profile_dt                         2021-11-22T16:53:28.531654
        6      myexp2    1   profile  2021-11-22T16:53:28.643665  eowyn   0.0   memory_load                                               22.4
        7      myexp2    1   profile  2021-11-22T16:53:28.651388  eowyn   0.0  memory_total                                        33542479872
        8      myexp2    1   profile  2021-11-22T16:53:28.658964  eowyn   0.0      cpu_load                           [25.9, 27.1, 27.6, 28.6]
        9      myexp2    1   profile  2021-11-22T16:53:28.666597  eowyn   0.0     cpu_count                                                  4
        10     myexp2    1   profile  2021-11-22T16:53:28.673986  eowyn   0.0      cpu_freq                       [0.833, 1.728, 2.228, 1.736]
        11     myexp2    1   profile  2021-11-22T16:53:28.681591  eowyn   0.0       cpu_avg                            [0.215, 0.6825, 0.6925]
        12     myexp2    1   profile  2021-11-22T16:53:28.688981  eowyn   0.0      disk_use                                               95.6
        13     myexp2    1   profile  2021-11-22T16:53:28.697768  eowyn   0.0    disk_total                                       502468108288
        14     myexp2    1      stop  2021-11-22T16:53:28.705661  eowyn   NaN           NaN                                                NaN


The following tracking providers are available:

* :code:`default` - the default tracker, :code:`OmegaSimpleTracker`
* :code:`profiling` - the profiling tracker, :code:`OmegaProfilingTracker`
* :code:`notrack` - the no-operation tracker, :code:`NoTrackTracker`. Use
  this to disable tracking.

