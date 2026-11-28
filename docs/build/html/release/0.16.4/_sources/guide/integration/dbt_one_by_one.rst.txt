Deploying dbt projects
======================

dbt projects can be deployed to run on the omega-ml runtime as an ad-hoc or a scheduled
job as follows. dbt projects are essentially a collection of files that make up a SQL-based
workflow. This means we can easily deploy dbt projects to omega-ml as a script, and run them
on schedule or on-demand.

1. Package the dbt project(s) and deploy to omega-ml
2. Schedule a job to run the dbt project(s)
3. Serve the dbt project(s) documentation via omegaml's apphub (or browse locally)

Here's a quick schematic overview of the components involved:

How to package a dbt project
------------------------------

To deploy a dbt project, we first need to package the project into a pip-installable package.
This can be done by the following steps:

1. Mark the dbt project as a python package (by creating a `__init__.py` file)
2. Create the `setup.py` and `MANIFEST.in` files in the dbt directory
3. Store the dbt project in `om.scripts`
4. Create a job (notebook) to run the dbt project on a schedule

Let's go through these steps in detail.

Create a dbt project
++++++++++++++++++++

We assume a dbt project exists already. If not, you can create a new dbt project by following these
steps. To create a dbt project, we can use the dbt CLI. First, we need to install dbt:

.. code-block:: bash

    $ pip install dbt-core

Then, we can create a new dbt project by running the following command:

.. code-block:: bash

    $ dbt init myproject

Mark your dbt project as a python package
+++++++++++++++++++++++++++++++++++++++++

To deploy a dbt project to omega-ml, we need to package the project as a python package so it can
be installed in the runtime. This includes essentially two files:

1. `__init__.py` to mark the dbt project as a python package
2. The dbt `profiles.yml` to specify the dbt profile (without any secrets)

Mark the dbt project as a python package by creating a `__init__.py` file in the db project directory. We
will also include a `profiles.yml` that however does not include any secrets such as passwords or API keys.
Instead, we will update the dbt profile at runtime with omega-ml defaults.

In `__init__.py` we will add a function to update the dbt profile with omega-ml defaults. This function
is used at run-time to replace `{PLACEHOLDER}`-style variables, e.g. to specify an SQL connection details
such as server hostnames and passwords which are provided as part of the omega-ml qualifier context
in which the dbt project will run.

The `__init__.py` file should look like this:

.. code-block:: python

    # /path/to/dbt/myproject/__init__.py
    def update_dbt_profile(fn=None, mod=None, om=None, **vars):
        """
        update dbt profiles.yaml with omegaml defaults

        Usage:
            import omegaml as om
            mod = om.scripts.get('dbt/foo', install=True)
            update_dbt_profile(mod=mod, om=om)
        """
        from pathlib import Path
        default_fn = Path(getattr(mod, '__file__', __file__)).parent / 'profiles.yml'
        fn = Path(fn) if fn else default_fn
        if not fn.exists():
            raise FileNotFoundError(f'dbt profiles.yml not found at {fn}')
        vars.update(**om.defaults) if om else None
        with open(fn, 'r') as f:
            profiles = f.read()
        with open(fn, 'w') as f:
            profiles = profiles.format(**vars)
            f.write(profiles)
        return fn.parent

Copy your profiles.yml from `$HOME/.dbt/profiles.yml`, and replace the values that are provided by
your omega-ml qualifier context with their respective `{OMEGA_VARIABLE}` placeholder.
Later we will use the `update_dbt_profile` function to replace these placeholders with the actual
values provided by omega-ml.

The `profiles.yml` file should look something like this (adopt to the specific variables used
in your omega-ml qualifier context):

.. code-block:: yaml

  myproject:
      target: prod
      outputs:
        prod:
          type: sqlserver
          driver: '{OMEGA_SQL_SERVER_DRIVER}' # (The ODBC Driver installed on your system)
          server: {OMEGA_SQL_SERVER_HOST}
          port: 1433
          database: {OMEGA_SQL_SERVER_DB}
          schema: schema_name
          user: {OMEGA_SQL_SERVER_USER}
          password: {OMEGA_SQL_SERVER_PASSWORD}

Create the setup.py and MANIFEST.in files
+++++++++++++++++++++++++++++++++++++++++++

The dbt project needs a `setup.py` file to be packaged as a python package. The `setup.py` file
should look like this:

.. code-block:: python

    #  /path/to/dbt/setup.py
    from setuptools import setup, find_packages

    setup(
        name='myproject',
        version='0.1',
        packages=find_packages(),
        include_package_data=True,
        install_requires=[
            'dbt-core',
        ]
    )

We also need a `MANIFEST.in` file to include the dbt project files (models, macros, etc.) in the package:

.. code-block:: script

    # myproject/MANIFEST.in
    include *.in
    recursive-include myproject *

Store the dbt project in `om.scripts`
+++++++++++++++++++++++++++++++++++++

Then, we can package the dbt project by running the following command:

.. code-block:: bash

    # in /path/to/setup.py
    $ om scripts put . myproject dbt/myproject

Schedule a job (notebook)
-------------------------

To run the dbt project on a schedule, we need to create a job (notebook) that runs the dbt project.
The notebook should look as follows and be stored in om.jobs. The notebook essentially has three
parts:

1. Import the dbt project and update the dbt profile with omega-ml defaults
2. Run the dbt project
3. Generate and save the dbt docs, so it is available for later inspection or
   serving via omegaml's apphub

.. code-block:: python

    [1] # cron: 0 0 * * 1
        # comment: run every Monday at midnight
    [2] # (1) import dbt project and prepare dbt profile
        import omegaml as om
        project = 'dbt/foo'
        dbt_mod = om.scripts.get(project, install=True)
        project_dir = dbt_mod.update_dbt_profile(om=om, OMEGA_BUCKET='main')
    [3] # (2) run dbt project
        !dbt run --profiles-dir $project_dir --project-dir $project_dir
    [4] # (3) generate docs and save to om.datasets as dbt/<project>/report.zip
        # generate docs
        !dbt docs generate --profiles-dir $project_dir --project-dir $project_dir --target-path report
        !python -m zipfile -c report.zip $project_dir/report
        !om datasets put ./report.zip $project/report.zip


Browse the dbt project documentation
------------------------------------

The dbt project documentation can be browsed locally by running the following command:

.. code-block:: bash

    # in /path/to/dbt/myproject
    $ om datasets get dbt/myproject/report.zip -o report.zip
    $ unzip report.zip
    $ dbt docs serve --target-path report

Alternatively, the dbt project documentation can be served via omegaml's apphub. To do this, we need to create a
a small flask app that serves the dbt project documentation, created and saved by the job (notebook) above.
The app should look as follows:

.. code-block:: python

    # add this to path/to/dbt/myproject/__init__.py
    def create_app(server=None, uri=None, **kwargs):
        import os
        import uuid

        from functools import lru_cache
        from flask import Flask, abort
        from flask import Blueprint
        from zipfile import ZipFile

        import omegaml as om

        server = server or Flask(__name__)
        server.config.setdefault('SECRET_KEY', os.environ.get('SECRET_KEY') or uuid.uuid4().hex)

        app = Blueprint('foo', __name__,
                        url_prefix=uri,
                        template_folder='templates')

        file_cache = lru_cache(maxsize=100)
        om = om.setup()

        @app.route('/')
        def index():
            # present a list of project reports stored in om.datasets
            # -- each project report is stored as dbt/<project>/report.zip
            href = "<a href='{uri}/{project}/index'>{project}</a><br>"
            projects = [href.format(project=os.path.basename(os.path.dirname(project)),
                                    uri=uri or '') for project in om.datasets.list('dbt/*')]
            text = "<p>select a project to view its dbt report</p>"
            return text + "\n".join(projects) if projects else "No projects found"

        @app.route('/<project>/index')
        def project(project):
            # open the project report's index.html
            _send_report_file.cache_clear()
            project_dir = f'dbt/{project}'
            return _send_report_file(project_dir, 'index.html')

        @app.route('/<project>/<path:path>')
        def static_file(project, path):
            # open a static file from the project report
            project_dir = f'dbt/{project}'
            return _send_report_file(project_dir, path)

        @app.errorhandler(404)
        def handle_exception(e):
            return {
                "code": e.code,
                "description": e.description,
                "exception": str(e),
            }, 404

        @file_cache
        def _send_report_file(project_dir, filename):
            report_fn = f'{project_dir}/report.zip'
            try:
                with om.datasets.get(report_fn) as f:
                    zipfile = ZipFile(f)
                    data = zipfile.read(f'report/{filename}')
                    zipfile.close()
            except Exception as e:
                abort(404, str(e))
            return data

        server.register_blueprint(app)
        return server


To run this app locally, we can use the following command:

    $ FLASK_APP=myproject:create_app flask run

To serve the app via omegaml's apphub, we need to package the app as a python package
and store it in om.scripts.

    $ om scripts put . myproject apps/myproject
    $ om runtime restart app myproject

Working with multiple dbt projects
==================================

If you have multiple dbt projects, you can either follow the same steps as above, applied
to each project, or you can create a single "dbtdeploy" application, that can be used
to run multiple dbt projects.

Here's how to create the "dbtdeploy" application:

1. Create a dbtdeploy application::

    # in /path/to/dbt
    $ mkdir dbtdeploy
    $ touch dbtdeploy/__init__.py
    $ touch dbtdeploy/setup.py
    $ touch dbtdeploy/MANIFEST.in

2. Update the `setup.py` and `MANIFEST.in` files:

    # dbtdeploy/setup.py
    from setuptools import setup, find_packages

    setup(
        name='dbtdeploy',
        version='0.1',
        packages=find_packages(),
        include_package_data=True,
        install_requires=[
            'dbt-core',
        ]
    )

    # dbtdeploy/MANIFEST.in
    include *.in
    recursive-include dbtdeploy *
    recursive-include myproject *
    <.. include other dbt projects here ..>

3. Update the __init__.py file for the dbtdeploy application::

    # include the update_dbt_profile function, from above
    def update_dbt_profile(fn=None, mod=None, om=None, **vars):
        <... copy from above verbabtim ...>

    # include the create_app function, from above
        <... copy from above verbabtim ...>


Now we can package the dbtdeploy application, including all dbt projects
into a single dbtdeploy application.

1. Link each dbt project into the directory of the dbtdeploy application::

    $ ln -s /path/to/dbt/myproject dbtdeploy/myproject

2. Package the dbtdeploy application::

    $ om scripts put . dbtdeploy dbt/dbtdeploy

Finally, we can use the dbtdeploy application to run multiple dbt projects.

1. Create a job (notebook) to run the dbtdeploy application::

    # in om.jobs
    [1] # cron: 0 0 * * 1
        # comment: run every Monday at midnight
    [2] # (1) import dbt project and prepare dbt profile
        dbtdeploy = om.scripts.get('dbt/dbtdeploy', install=True)
        dbt_dir = Path(dbtdeploy.__file__).parent
        dbtdeploy.update_dbt_profile(f"{dbt_dir}/profiles.yml", om=om)
    [3] # (2) run dbt projects (repeat (2) and (3) for each dbt project)
        project_dir =  dbt_dir / 'foo`
        !dbt run --profiles-dir $dbt_dir --project-dir $project_dir
    [4] # (3) generate docs and save to om.datasets as dbt/<project>/report.zip
        # generate docs
        !dbt docs generate --profiles-dir $dbt_dir --project-dir $project_dir --target-path report
        !python -m zipfile -c report.zip $project_dir/report
        !om datasets put ./report.zip $project/report.zip

2. Serve the dbt project documentation via omegaml's apphub::

    # package the app
    $ om scripts put . dbtdeploy apps/dbtdeploy
    $ om runtime restart app dbtdeploy

    Alterantively, you can serve the app locally by running the following command:

    $ FLASK_APP=dbtdeploy:create_app flask run