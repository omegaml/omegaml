Working with Python
===================

omega-ml is easiest to use from Python. In any Python program, notebook
or shell:

.. code-block:: python

    import omegaml as om

    # try a few things
    om.datasets.list()
    om.models.list()

    # store
    df = pd.DataFrame( ... )
    om.datasets.put(df, 'mydf')

    # retrieve
    om.datasets.get('mydf')

Using omega-ml in python
------------------------

Starting up omega-ml is straight forward. In any Python program or interactive
shell just import the :code:`omegaml` module as follows:

.. code:: python

   import omegaml as om

The :code:`om` module is readily configured to work with your local omega-ml
server, or with the cloud instance configured using the :code:`om cloud login`
command.

Once loaded :code:`om` provides several storage areas that are immediately usable:

* :code:`om.datasets` - storage area for Python and Pandas objects
* :code:`om.models` - storage area for models
* :code:`om.scripts` - storage area for custom modules (a.k.a. lambda modules)
* :code:`om.jobs`- storage area for jobs (ipython notebooks)

In addition, your cluster or cloud resources are available as

* :code:`om.runtime` - the omega-ml remote execution environment


Getting help
++++++++++++

To get help on stored objects use the per-object .help() method. This will
show the doc string of the plugin for that object. To get help on functions,
use Python's built-in help().

For example:

.. code:: python

    # per object help
    om.datasets.help('mydataset')
    om.models.help('mymodel')

.. code:: python

    help(om.datasets)
    help(om.datasets.put)
    help(om.dataests.getl('mydata'))
    help(om.runtime)


Running a worker
----------------

.. code:: bash

    $ om runtime celery worker

