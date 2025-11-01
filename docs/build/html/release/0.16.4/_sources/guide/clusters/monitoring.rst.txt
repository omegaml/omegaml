Monitoring the runtime
======================

.. contents::

Using the cli
-------------

The omega-ml cli provides the :code:`runtime status` command to inspect the
status.

.. code:: bash

    # show all active workers
    $ om runtime status
    {'celery@eowyn': []}

    # show active labels, as processed by workers
    $ om runtime status labels
    {'celery@eowyn': ['default:R']}

    # show worker statistics
    {'celery@eowyn': {'size': 4,
                  'tasks': {'omegaml.tasks.omega_ping': 1,
                            'omegaml.tasks.omega_predict': 7}}}


Using the console
-----------------

.. _celery events: https://docs.celeryproject.org/en/stable/userguide/monitoring.html#celery-events-curses-monitor

The `celery events`_ console application will show live events across all workers.

.. code:: bash

    $ om runtime celery events

.. image:: /images/celery_events.png


Using a browser
---------------

.. _celery flower: https://docs.celeryproject.org/en/stable/userguide/monitoring.html#flower-real-time-celery-web-monitor

The `celery flower`_ web application provides both insights into the currently
running tasks as well as history statistics.

.. code:: bash

    $ pip install omegaml flower
    $ om runtime celery flower

.. image:: /images/celery_flower.png


Using celery commands
---------------------

.. _celery command-line utilities: https://docs.celeryproject.org/en/stable/userguide/monitoring.html#management-command-line-utilities-inspect-control

Further inspection and control of the omega-ml runtime is provided by
the `celery command-line utilities`_. Most of these commands are directly
available through the :code:`om runtime celery` command:

.. code:: bash

    $ om runtime celery inspect ping
    -> celery@eowyn: OK
               pong

Note that omega-ml ensures proper initialisation of the celery environment.
However it is also possible to interact with celery directly. In some instances
this may be more convenient.

.. code:: bash

    $ celery -A omegaml.celeryapp inspect ping
    -> celery@eowyn: OK
           pong




