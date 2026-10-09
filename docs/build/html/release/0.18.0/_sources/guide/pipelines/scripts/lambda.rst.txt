Using pip-installable modules
=============================

.. _serverless functions:: https://de.wikipedia.org/wiki/Function_as_a_Service

omega-ml supports execution of arbitrary modules packaged by pip on the runtime cluster. This
is the equivalent of `serverless functions`_ with the bonus of having the full set of omega-ml capabilities
available to your modules.

Writing a pip-installable Module
--------------------------------

Creating a pip-installable Module is straight forward:

1. write your code
2. add :code:`setup.py`
3. use :code:`om.scripts.put()` to deploy the package

To make your code executable through the REST API or in :code:`om.runtime.script` your
code's top-level package must contain a :code:`run()` method:

.. code::

   def run(om, *args, **kwargs):
        ...


The :code:`om` argument is the omega instance. Inside a lambda module you should always
use this instance instead of importing omegaml explicitely. This is to ensure the instance
is properly initialized.

:code:`kwargs` will contain the key/value pair passed to the module on execution.

The simplest :code:`setup.py` is as simple as follows:

.. code::

    from distutils.core import setup
    setup(name='helloworld', version='1.0',
          description='simple omegaml hello world script', author='omegaml',
          author_email='info@omegaml.io', url='http://omegaml.io',
          packages=['helloworld'],)


Deploying a module
------------------

To deploy a script programmatically use :code:`om.scripts.put()`.

.. code::

    # the pkg:// prefix triggers the python.package plugin
    om.scripts.put('pkg://path/to/helloworld`, 'helloworld')

Alternatively use the cli to achieve the same:

.. code::

    $ om scripts put ./path/to/helloworld helloworld


This will build the package and store it in omega-ml. It is automatically
available for execution using the REST API or :code:`om.runtime.script()`.

Learning more about pip and setuptools
--------------------------------------

While the above provides a concise introduction to wrinting pip-installable
modules, this can be a complex topic. More information can be found at the
following locations:

*Official tutorials*

* https://packaging.python.org/en/latest/tutorials/packaging-projects/
* https://setuptools.pypa.io/en/latest/userguide/quickstart.html

*Community guides*

* https://the-hitchhikers-guide-to-packaging.readthedocs.io/en/latest/quickstart.html
* https://python-packaging-tutorial.readthedocs.io/en/latest/setup_py.html
* https://flask.palletsprojects.com/en/2.0.x/patterns/distribute/


Executing a module
------------------

Using the REST API
++++++++++++++++++

Use the :code:`/api/script/` REST API to execute a module:

.. code::

    POST /api/script/hellworld/?param=value
    =>
    {
        'script': 'helloworld'
        'kwargs': { 'param': value },
        'result': <result>,
        'runtime': <microseconds>,
        'started': 'datetime in iso 8601 format',
    }


Using the runtime API
+++++++++++++++++++++

Use the :code:`om.runtime.script(<name>)` API to run a module on the cluster:

.. code::

    result = om.runtime.script('helloworld').run(foo='bar')
    result.get()
    =>
    {
        'script': 'helloworld'
        'kwargs': { 'foo': 'bar' },
        'result': <result>,
        'runtime': <microseconds>,
        'started': 'datetime in iso 8601 format',
    }


