Experiment tracking
===================

omega-ml provides experiment tracking for model development,
testing and production use.

A simple example
----------------

To set up experiment tracking, we specify the experiment
as a context to the runtime:

.. code::

    with om.runtime.experiment('myexp') as exp:
        score = lr.score(X, Y)
        exp.log_metric('accuracy', score)

To retrieve the experiment's data, we can get the experiment
from the models data store:

.. code::

    exp = om.models.get('experiments/myexp')
    data = exp.data()
