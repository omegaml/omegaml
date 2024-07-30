Automated Drift Monitoring
==========================

In a production scenario where models are deployed and serving predictions, it is important to monitor the
model's performance and the data it is receiving. omega-ml provides a way to automate this monitoring process
by attaching a DriftMonitor object to a model, and scheduling it to run at regular intervals.

As an example, let's say we have a model that predicts housing prices in California, using the scikit-learn
california dataset. We can attach a DriftMonitor to the model, and schedule it to run daily.

.. code::

    # create a basic model
    from sklearn.linear_model import LinearRegression
    from sklearn.datasets import fetch_california_housing

    california = fetch_california_housing(as_frame=True)
    reg = LinearRegression()
    reg.fit(california.data, california.target)
    om.models.put(reg, 'california')

    # setup the drift monitor
    with om.runtime.experiment('housing', autotrack=True) as exp:
        exp.track('california', monitor=True, schedule='daily')

The DriftMonitor will take snapshots of the input and target features of the model, and compare them to a baseline
snapshot. If the distribution of the features has changed significantly, the DriftMonitor will raise an alert.

First, let's create a baseline snapshot of the model's input and target features.

.. code::

    with om.runtime.experiment('housing', autotrack=True) as exp:
        mon = exp.as_monitor('california')
        mon.snapshot('california', X=california.data, Y=california.target)

Let's say the model has been running for a few days, and we want to check if there is a concept or model
drift, that is P(Y|X) has changed.

Now, let's simulate a change in the target predictions, relative to the input features. We can do this by
simulating a number of predictions, however using only a fraction of the input.

.. code::

    model = om.runtime.model('california')
    yhat = model.predict(california.data.sample(frac=0.1)

Since we have defined the experiment to be autotracking, the `predict()` method's input (X) and output (Y)
is automatically logged.

.. code::

    exp.data(event='predict', run=-1)

.. image:: /images/mon_autotrack_0.png

The DriftMonitor will regularily take snapshots of all predictions the current snapshot
to the baseline snapshot, and log an alert. For illustration, let's do this manually.

.. code:: python

        mon.capture()
        exp.data(event=['drift', 'alert'], run=-1)

.. image:: /images/mon_autotrack_1.png

.. code:: python



.. code::

    california_noisy = california.data + 0.1 * np.random.randn(*california.data.shape)
    with om.runtime.experiment('housing', autotrack=True) as exp:
        mon = exp.as_monitor('california')
        mon.snapshot('california', X=california_noisy, Y=california.target)

When the DriftMonitor runs, it will compare the current snapshot to the baseline snapshot, and raise an alert if





