Working with models
===================

.. code:: bash

    $ om models -h
    Usage:
      om models list [<pattern>] [--raw] [-E|--regexp] [options]
      om models put <module.callable> <name>
      om models drop <name>
      om models metadata <name>


Storing a model
---------------

Models can be stored directly from any of your project's Python modules.

1. create a Python module and a callable that returns your model instance

    .. code:: python

        # mymodule.py
        from sklearn.linear_model import LinearRegression

        def create_model():
            reg = LinearRegression()
            return reg

2. Use the cli to store the model

    .. code:: bash

        $ om models put mymodule.create_model regmodel
        Metadata(name=regmodel,bucket=omegaml,prefix=models/,kind=sklearn.joblib,created=2021-02-18 20:55:07.161042)

    This will call the :code:`create_model()` function and store the
    resulting model as :code:`regmodel`. The model is stored in as returned.
    The :code:`create_model` can return an unfitted, a fitted or a partially
    fitted model.

3. Use the Python shell

    .. code:: python

        $ om shell
        [] from mymodule import create_model

           mdl = create_model()
           om.models.put(mdl, 'regmodel')
           => Metadata(name=regmodel,bucket=omegaml,prefix=models/,kind=sklearn.joblib,created=2021-02-18 20:55:07.161042)

Listing models
--------------

Listing models follows the common pattern syntax. No pattern is equal to
the generic pattern :code:`*`, which finds all contents


.. code:: bash

   $ om models list reg*
   ['regmodel']


Using the :code:`--raw` option prints the corresponding Metadata entries:

.. code:: bash

   $ om models list reg* --raw
   [<Metadata: Metadata(name=regmodel,bucket=omegaml,prefix=models/,kind=sklearn.joblib,created=2020-06-18 14:38:30.627000)>]


Dropping models
---------------

Dropping models requires the specific model name:

.. code:: bash

   $ om models drop regmodel
   True

If the model does not exist the command will print an error message:

.. code:: bash

   $ om models drop regmodel
   *** ERROR


Showing a model's metadata
--------------------------

A models' metadata is shown as a JSON object.

.. note::

   The content of the metadata is specific to the model's type.

.. code:: bash

    $ om models metadata regmodel
    {
      "_id": {
        "$oid": "602ec61b0664b73eb299d1e5"
      },
      "name": "regmodel",
      "bucket": "omegaml",
      "prefix": "models/",
      "kind": "sklearn.joblib",
      "kind_meta": {
        "_om_backend_version": "1"
      },
      "attributes": {
        "versions": {
          "tags": {
            "latest": "b434c293f03a925a3932895ca1f11a7144093db7"
          },
          "commits": [
            {
              "name": "_versions/regmodel/b434c293f03a925a3932895ca1f11a7144093db7",
              "ref": "b434c293f03a925a3932895ca1f11a7144093db7"
            }
          ],
          "tree": {
            "b434c293f03a925a3932895ca1f11a7144093db7": "latest"
          }
        }
      },
      "s3file": {},
      "created": {
        "$date": 1613681707161
      },
      "modified": {
        "$date": 1613681707433
      },
      "gridfile": {
        "$oid": "602ec61b0664b73eb299d1e3"
      }
    }



