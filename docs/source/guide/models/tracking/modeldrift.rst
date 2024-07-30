Model Drift
-----------

Monitoring model drift is similar to monitoring data drift. We create a model `m1` and take snapshots
of two sets of predictions on a dataset. We then compare the two snapshots and plot the results.

.. code:: python

    import omegaml as om
    from omegaml.backends.monitoring import ModelDriftMonitor
    from sklearn import datasets

    x, y = datasets.load_iris(return_X_y=True, as_frame=True)

    with om.runtime.experiment('foo', recreate=True) as exp:
        mon = ModelDriftMonitor(tracking=exp)
        mon.snapshot(X=x, Y=y, catcols=['target'])
        mon.snapshot(Y=y[0:5], catcols=['target'])

    stats = mon.compare()
    stats.plot()

.. image:: /images/mon_1hist_drift.png


