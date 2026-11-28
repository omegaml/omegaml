Scheduling notebooks
====================

*This explores using the command line to work with notebooks. The same also
works with the integrated Jupyter notebook*

Jupyter Notebooks are great tools for exploratory and ad-hoc work. But how do you
run a notebook on a schedule? Say you have a notebook that produces a nice report,
and it should run every Friday morning.

With omega|ml, scheduling a notebook to run in the cloud is straight forward:

.. code:: bash

    # make it run every Friday morning
    $ om jobs schedule mynotebook "Fridays, at 06:00"

We can verify the next times this notebook will be run:

.. code:: bash

    $ om jobs schedule mynotebook show --next 10
    Currently mynotebook is scheduled at Every minute, only on Friday
    Given this existing interval, next 10 times would be:
      2020-09-18 13:35:00
      2020-09-18 13:36:00
      2020-09-18 13:37:00
      2020-09-18 13:38:00
      2020-09-18 13:39:00
      2020-09-18 13:40:00
      2020-09-18 13:41:00
      2020-09-18 13:42:00
      2020-09-18 13:43:00
      2020-09-18 13:44:00
    mynotebook is scheduled to run next at 2020-09-18T13:35:00

For each run the notebook, including all output, will be stored in `jobs/results`, and
we can get it back:

.. code:: bash

    $ om jobs list results
    ['mynotebook.ipynb', 'mynotebook2.ipynb', 'results/mynotebook_2020-09-18 13:37:56.885840.ipynb']

    $ om jobs get 'results/mynotebook_2020-09-18 13:37:56.885840.ipynb' mynotebook_results.ipynb


