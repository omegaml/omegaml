Monitoring model and data drift
===============================

.. toctree::
    :maxdepth: 1

    tracking
    datadrift
    modeldrift
    automonitoring
    basics


What is drift monitoring?
-------------------------

Drift monitoring is the process of detecting changes in the distribution of a model's input features and
targets over time. omega-ml implements drift monitoring by taking statistical snapshots of input and
target features at regular intervals and comparing each snapshot to a baseline snapshot.

There are two types of drift:

* Data Drift: Changes in the distribution of input features. We're interested in P(X) changing over time.
* Model or Concept Drift: Changes in the distribution of target features. We're interested in P(Y|X) changing
  over time.

omega-ml implements both data and concept drift using the concept of a Monitor. A Monitor is an instance of
an object that takes snapshots of data and compares them to a baseline snapshot. The Monitor can be used
interactively, in code, or run automatically on a schedule.

