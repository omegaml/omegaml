Using mlflow projects
=====================

.. _mlflow: https://mlflow.org/

omega-ml runs `mlflow_` projects from a local file or from a git repository
to form a cloud-agnostic runtime platform for easy remote pipeline execution.

Deploying a local mlflow project
--------------------------------

.. code:: python

    # deploy the mlflow project to omega-ml runtime
    mlflow_path = '/path/to/mlflow/project'
    meta = om.scripts.put(mlflow_path, 'myproject', kind='mlflow.project')

    # run the project in a remote runtime worker
    om.runtime.script('myproject').run(entry_point='main.py', conda=False)

As an alternative to specify :code:`kind=mlflow.project`, we can use
the :code:`mlflow://` prefix:

.. code:: python

    mlflow_path = 'mlflow:///path/to/mlflow/project'
    meta = om.scripts.put(mlflow_path, 'myproject', kind='mlflow.project')


Deploying a git-based mlflow project
------------------------------------

.. code:: python

    # deploy the mlflow project to omega-ml runtime from github
    project_path = 'https://github.com/mlflow/mlflow#examples/quickstart'
    meta = om.scripts.put(mlflow_path, 'myproject', kind='mlflow.project')

    # run the project in a remote runtime worker
    om.runtime.script('myproject').run(entry_point='mlflow_tracking.py', conda=False)

As an alternative to specify :code:`kind=mlflow.gitproject`, we can use
the :code:`mlflow+ssh://` prefix:

.. code:: python

    # deploy the mlflow project to omega-ml runtime from github
    project_path = 'mlflow+ssh://git@github.com/mlflow/mlflow#examples/quickstart'
    meta = om.scripts.put(mlflow_path, 'myproject')

    # run the project in a remote runtime worker
    om.runtime.script('myproject').run(entry_point='mlflow_tracking.py', conda=False)


Disclaimer and License
----------------------

.. _mlflow_license: https://github.com/mlflow/mlflow/blob/master/LICENSE.txt

mlflow is not part of, distributed by or along of omega-the. The above
describes API-binding interfaces to mlflow, but does not itself constitute
a derivative work of mlflow as per the `mlflow_license`_.
