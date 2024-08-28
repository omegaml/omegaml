Working with notebooks
======================

Integrated JupyterLab
---------------------

omega|ml comes pre-configured to run with JupyterLab. In this mode, every
notebook that you create is automatically stored in the omega|ml :code:`jobs`
storage. The advantage is that you can share notebooks instantly with your
colleagues - their JupyterLab workspace will show the same notebooks as you have,
no matter from where they work.

Local JupyterLab
----------------

If you prefer to work within your own JupyterLab environment, you can still
use omega|ml to deploy your notebooks and run the on the cloud. This is
convenient, for example when you only have a certain budget to run on a CPU.
Then you can prepare your notebooks locally and only run them on the GPU when
it is ready.

In this case you have to store your notebook to :code:`jobs` as follows. See
the next section for running it on the cloud.

.. code:: python

    # store a notebook in omegaml
    $ om jobs put /path/to/notebook.ipynb mynotebook


Running notebooks on the cloud
==============================

To run the notebook, waiting for its result, and store the result in `jobs/result`, execute
the following command:

.. code:: bash

    $ om runtime job mynotebook

You may also run the notebook asynchronously, as a background task, as follows. The command will
print the task id for later retrieval of the job's result:

.. code:: bash

    $ om runtime job mynotebook --async
    77e50b76-b4bb-4411-a407-fa1cf2162f81

    $ om runtime result 77e50b76-b4bb-4411-a407-fa1cf2162f81
    <Metadata: Metadata(name=results/Untitled_2020-10-06 18:41:00.060559.ipynb,bucket=omegaml,prefix=jobs/,kind=script.ipynb,created=2020-10-06 18:41:01.942656)>

Retrieving results
------------------

.. code:: bash

    $ om jobs list results
    ['mynotebook.ipynb', 'mynotebook2.ipynb', 'results/mynotebook_2020-09-18 13:37:56.885840.ipynb']

We can get it back or view it directly in JupyterLab:

.. code:: bash

    $ om jobs get 'results/mynotebook_2020-09-18 13:37:56.885840.ipynb' mynotebook_results.ipynb



