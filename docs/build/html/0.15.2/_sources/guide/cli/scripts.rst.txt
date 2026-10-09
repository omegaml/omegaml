Working with scripts
====================

.. code:: bash

   $ om scripts -h
   Usage:
    om scripts list [<pattern>] [--raw] [--hidden] [-E|--regexp] [options]
    om scripts put <path> <name> [options]
    om scripts get <name>
    om scripts drop <name> [options]
    om scripts metadata <name>

.. note:: How scripts work

   omegaml scripts are simply pip-installable modules that expose a :code:`run()` function returning
   a pickle-serializable result. omegaml works like a thin wrapper around the Python standard tools
   setuptools and pip modules:

   * Upon storing a script, omegaml creates a package and stores it its distributed filesystem.
   * Upon retrieving a script, the package is installed. Packages are created using
     :code:`python setup.py sdist`. Packages are installed using :code:`pip install <package>`.
   * In case of remotely hosted packages, omegaml stores the reference to the remote
     location. In this case `python setup.py sdist` is not run. If you have stored a local
     package and wish to replace it by a remote reference, drop the package first as
     local and remote packages result in different :code:`Metadata kind` types, respectively.

Packaging local modules
-----------------------

.. _install_requires: https://packaging.python.org/guides/distributing-packages-using-setuptools/#install-requires

Scripts are pip-installable packages. To package-up a script and store it, specify the :code:`<path>`
to the :code:`setup.py`:

.. code:: bash

    $ om scripts put process/setup.py process
    running sdist
    running check
    warning: sdist: manifest template 'MANIFEST.in' does not exist (using default file list)

    writing manifest file 'MANIFEST'
    creating process-1.3
    creating process-1.3/process
    making hard links in process-1.3...
    hard linking README -> process-1.3
    hard linking setup.py -> process-1.3
    hard linking process/__init__.py -> process-1.3/process
    Creating tar archive
    removing 'process-1.3' (and everything under it)
    Metadata(name=process,bucket=omegaml,prefix=scripts/,kind=python.package,created=2020-08-28 13:58:32.407000)

.. note::

   * The name of the package created must be the importable module name
   * The name of the package must contain alphanumeric characters only
   * Scripts can import other modules by specifying dependencies. See install_requires_ in the
     Python packaging guide


In this example, the following directory structure, setup.py and code was used:

.. code:: bash

    # structure
    ./setup.py
    ./process/__init_.py

    # setup.py
    #!/usr/bin/env python
    from distutils.core import setup
    setup(name='process',
          version='1.3',
          description='simple omegaml hello world script',
          author='omegaml',
          author_email='info@omegaml.io',
          url='http://omegaml.io',
          packages=['process'])

    #__init__.py
    def run(om, *args, **kwargs):
        return "hello world"

Packaging pypi-hosted modules
-----------------------------

Instead of building and packaging modules it is possible to store a reference to
a specific Pypi-hosted module:

.. code:: bash

   $ om scripts put "six==1.0" six

Upon installation, the script will be pulled from pypi and installed as usual:

.. code:: bash

    $ om scripts get six
    Collecting six==1.0
      Downloading six-1.0.0.tar.gz (11 kB)
    Building wheels for collected packages: six
      Building wheel for six (setup.py) ... done
      Created wheel for six: filename=six-1.0.0-py3-none-any.whl size=4871 sha256=c966e8ada020a84af438ca7a1baf0e0597200d84f82f704425a4a00885b29e66
      Stored in directory: /tmp/pip-ephem-wheel-cache-3f58ar72/wheels/c5/45/ed/be3d9e59c2233eb179a23b38d5a74b20b139c689fcf16f9ca5
    Successfully built six
    Installing collected packages: six
    Successfully installed six-1.0.0


Packaging git-hosted modules
----------------------------

.. _pip vcs support: https://pip.pypa.io/en/stable/reference/pip_install/#vcs-support

Instead of building and packaging modules it is possible to store references to
git-hosted modules, using the `pip vcs support`_

.. code:: bash

    $ om scripts put "git+https://github.com/omegaml/apps.git#egg=helloworld&subdirectory=helloworld" helloworld

Upon installation, the script will be cloned from the git repository and installed as usual:

.. code:: bash

    $ om scrpits get helloworld
    Collecting helloworld
      Cloning https://github.com/omegaml/apps.git to /tmp/pip-install-yn92_8a9/helloworld_20e05893ad1d4e92bafbc281eb121236
      Running command git clone -q https://github.com/omegaml/apps.git /tmp/pip-install-yn92_8a9/helloworld_20e05893ad1d4e92bafbc281eb121236
    Building wheels for collected packages: helloworld
      Building wheel for helloworld (setup.py) ... done
      Created wheel for helloworld: filename=helloworld-1.0-py3-none-any.whl size=2192 sha256=d8b8cac1ad5e8a1c3f9dcc46cbf10634acb2f7e09e81ffc9ff0f6c38d0f08219
      Stored in directory: /tmp/pip-ephem-wheel-cache-p9kxp493/wheels/3d/10/b9/be33eac8519a9ae4dd329947255f240b5ccde8d01554155f5e
    Successfully built helloworld
    Installing collected packages: helloworld
    Successfully installed helloworld-1.0


Installing modules
------------------

A module can be installed as follows:

.. code:: bash

    $ om scripts get helloworld
    ...
    Successfully installed helloworld-1.0


Running scripts remotely
------------------------

Scripts are executed by the runtime as follows

.. code:: bash

    $ om runtime script helloworld
    {"script": "helloworld", "kwargs": {"pure_python": false}, "result": "hello world", "runtimes": 0.090067, "started": "2021-02-20T16:30:35.837488", "ended": "2021-02-20T16:30:35.927555"}


Running scripts locally
------------------------

.. _Celery: https://docs.celeryproject.org/en/stable/

Scripts can be executed locally instead of the the runtime by specifying the :code:`--local` flag.
Use this for debugging:

.. code:: bash

    $ om runtime script helloworld --local
    ...
    Successfully installed helloworld-1.3
    Task omegaml.backends.package.tasks.run_omega_script[329e6fb1-d2d6-4a24-881d-b17c9c917910] succeeded in 4.052356380969286s: '{"script": "process", "kwargs": {"pure_python": false}, "result": "Metadata(name=model_results,bucket=omegaml,prefix=data/,kind=python.data,created=2021-02-11 08:40:38.655000)", "runtimes": 0.308365, "started": "2021-02-20T17:34:33.057252", "ended": "2021-02-20T17:34:33.365617"}'
    {"script": "helloworld", "kwargs": {"pure_python": false}, "result": "hello world", "runtimes": 0.090067, "started": "2021-02-20T16:30:35.837488", "ended": "2021-02-20T16:30:35.927555"}

.. note::

    omegaml leverages Celery for local and remote executing of scripts:

    1. Ask Celery to run a task ("execute the run_omega_script task for script "helloworld")
    2. Celery receives the message, starts the corresponding task
    3. :code:`om.scripts.get()` installs the script in the runtime's environment (local or remote)
    4. :code:`import helloworlds` imports the module
    5. call :code:`helloworld.run(...)` and return its results

    To learn about Celery and its distributed task model see Celery_
