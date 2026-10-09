Testing your installation
=========================

After omega|ml is setup and is ready to function, you can test to see if
the setup is configured well using few example scripts we have shipped
with omegaml. Example scripts are located in
``<libdir>/omegaml/omegaml/examples/`` As of now we have included two
examples for the two backends we support ``SciKitLearn`` and ``Spark``.

SciKitLearn
-----------

To test against scikit learn, go to
``<libdir>/omegaml/omegaml/examples/`` and run

::

    # ./duplicate.py --broker-url $OMEGA_BROKER --queue celery --exchange celery --mongo-url $OMEGA_MONGO_URL --collection store

Spark
-----

To test against spark, go to ``<libdir>/omegaml/omegaml/examples/`` and
run

::

    # ./sparktest.py --broker-url $OMEGA_BROKER --queue celery --exchange celery --mongo-url $OMEGA_MONGO_URL --collection store
