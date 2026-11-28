Deploying web applications
==========================

.. _hello flask: https://github.com/omegaml/apps/tree/master/helloflask

.. contents::


Similarly to script modules omega-ml can deploy Flask-based applications using
the commercial edition's apphub component. An example Flask application is
provided at `hello flask`_

Deploying a local flask app
---------------------------

.. code:: bash

    $ git clone git+https://github.com/omegaml/apps/tree/master/helloflask
    $ om scripts put ./helloflask/setup.py apps/helloflask
    $ om runtime restart apps/helloflask

After a few moments, the application is available at
https://omegaml.io/apps/account/helloflask


Deploying a git-based flask app
-------------------------------

.. code:: bash

    $ GITURL="git+https://github.com/omegaml/apps/tree/master/helloflask"
    $ om scripts put $GITURL apps/helloflask
    $ om runtime restart apps/helloflask

After a few moments, the application is available at
https://omegaml.io/apps/account/helloflask

Deploying arbitrary docker images
---------------------------------

.. _k8s pod: https://kubernetes.io/docs/concepts/workloads/pods/

apphub is able to launch any docker image in a k8s pod, provided the
pod serves a http-based web application at a well-defined port
(defaults to port 80). This is only supported via the Python API.

.. code:: python

    appdef = {
        'appdef': {
            'image': 'nginx'
        }
    }
    om.scripts.put('https://github.com/omegaml/apps/tree/master/helloworld',
                   'apps/myapp', attributes=appdef)


When saved, launch the application:

.. code:: bash

    $ om runtime restart apps/myapp

After a few moments, the application is available at
https://omegaml.io/apps/account/myapp

:code:`appdef` can contain the following keys. See apphub.OmegaCloudRegistry
for details.

.. code::

    'image': the image to be used, defaults to env:APPHUB_POD_IMAGE or omegaml/apphub:latest
    'port': the port, defaults to 80
    'pullPolicy': defaults to env:APPHUB_POD_PULLPOLICY or IfNotPresent
    'pullSecret': defaults to env:APPHUB_POD_PULLSECRET or omegamlee-secreg
    'name': the deployment and pod name suffix, defaults to 'apphub'
    'configmap': the name of a k8s configmap, defaults to
    'deployment_file': defaults to apphub/resources/deployment.yml, must exist in the
        file system of the pod running apphub



Caveats
-------

To switch between local and git-based deployment, delete the existing script.
Otherwise omega-ml will not recognize the changed :code:`kind:`.

.. code:: bash

    # delete the local-deployed script first, then add the git URL
    $ om scripts drop apps/helloflask
    $ om scripts put $GITURL apps/helloflask



