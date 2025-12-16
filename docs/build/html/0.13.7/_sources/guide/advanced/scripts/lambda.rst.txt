Lambda Modules
==============

omega|ml supports execution of arbitrary modules packaged by pip on the runtime cluster. This
is the equivalent of AWS Lambda with the added bonus of having the full set of omega|ml capabilities
available to your modules.

Writing a Lambda Module
-----------------------

Creating a Lambda Module is straight forward:

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

To deploy a Lambda module use :code:`om.scripts.put()`:

.. code::

    om.scripts.put('pkg://path/to/helloworld`, 'helloworld')

This will build the package and store it in omega|ml. It is automatically
available for execution using the REST API or :code:`om.runtime.script()`.


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


