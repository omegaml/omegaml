Local setup using Vagrant
===========

OmegaML comes with a Vagrant resourcefile that can be used to spin off a
local machine that has spark, omegaml and hadoop all configured, integrated and ready to use.

Pre-requisites
--------------

Before you spin up the Vagrant machine, please make sure that you have a
working rabbitmq and mongodb installations and map the relative omegaml
variables to the same, which can be easily done using.

::

    $ export OMEGA_MONGO_URL=mongodb://<host ip>:27017/omega
    $ export OMEGA_BROKER=amqp://guest@<host ip>:5672//

Start up vagrant machine
------------------------

To start the vagrant machine, go to the installation directory of
omegaml, which would generally be
``<libdir>/omegaml/omegaml/resources/spark_vagrant`` where ``libdir``
would be the location where you installed omegaml.

::

    # cd <libdir>/omegaml/omegaml/resources/spark_vagrant
    # vagrant up

This will take a while and spin off a virtualbox with spark & omegaml on
it.

Using the vagrant machine
-----------------------

-  Open a web browser and browse http://localhost:18888 . This is the
   ipython notebook server.
-  Start a python notebook.
-  Run your code snippets.
-  To have omegaml run periodic jobs, create a notebook prefixing job\_
   to its name and the first cell with job parameters. Which should look
   something like below

   ::

       # omegaml.script:
       #   run-at: "*/1 * * * *"
       #   results-store: gridfs
       #   author: exsys@nixify.com
       #   name: Gaurav Ghimire

   In the above configuration, below points are to be noted :

   -  all job configurations should be valid yaml files.
   -  all lines must start with # .
   -  the first line should always be omegaml.script.
   -  run-at: “\ */1 * \* \* \*" defines the time interval in ‘cron’
      like schedule, this is scheduled to run every minute
   -  results-store: gridfs , results-store can either be s3 or gridfs

      -  s3 would store the results in pre-configured S3 bucket/path.
      -  gridfs would store the results as result\_.ipynb on same
         collection.
      -  author and name are author identifiers, not used for now, but
         may later be used for say email results.

Debugging
---------

To see omegaml and ipython logs

::

    @host$ vagrant ssh
    @vm$ tail -f /tmp/celeryd.log
    @vm$ tail -f /tmp/ipython.log
