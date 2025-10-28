Working with datasets
=====================

.. code:: bash

    $ om datasets -h
    Usage:
      om datasets list [<pattern>] [--raw] [-E|--regexp] [options]
      om datasets put <path> <name> [--replace] [--csv=<param=value>]... [--format csv|image|binary] [options]
      om datasets get <name> <path> [--csv <param>=<value>]... [options]
      om datasets drop <name> [--force] [options]
      om datasets metadata <name> [options]


Storing a dataset
-----------------

The cli supports storing the following types of datasets:

* csv files
* image files
* binary files

For csv files, the :code:`<path>` can be a local path, S3 URI, azure Blob
Storage URI, http source, webhdfs, or scp path. See the smart_open library for
details.

To store a csv:

.. code:: bash

    # -- python equivalent to om.datasets.read_csv('sample.csv', 'sample')
    $ om datasets put sample.csv sample
    Metadata(name=sample,bucket=omegaml,prefix=data/,kind=pandas.dfrows,created=2021-02-12 15:34:38.633000)

To store images or binary files

.. code:: bash

    $ om datasets put lenna.png lenna
    Metadata(name=lenna,bucket=omegaml,prefix=data/,kind=ndarray.bin,created=2021-02-20 09:19:58.788435)

To store any other file as a file

.. code:: bash

    $ om datasets put lenna.zip lenna.zip
    Metadata(name=lenna.zip,bucket=omegaml,prefix=data/,kind=python.file,created=2021-02-20 09:21:30.882209)

To work with remote files:

.. code:: bash

    $ om datasets put --format csv https://www.openml.org/data/get_csv/61/dataset_61_iris.arff iris


Retrieving a dataset
--------------------

The cli supports retrieving the same types of datasets and store the contents to a local or remote
path:

* csv files
* image files
* binary files

For csv files, the :code:`<path>` can be a local path, S3 URI, azure Blob
Storage URI, http source, webhdfs, or scp path. See the smart_open library for
details.

To retrieve a dataset

.. code:: bash

    $ om datasets get iris iris.csv

To transfer a dataset to a remote location

.. code:: bash

    $ om datasets get iris s3://mybucket/iris.csv


Working with remote files
-------------------------

.. _smart_open: https://pypi.org/project/smart-open/

Remote files are supported by providing a valid URL to a remote location. The cli uses
the smart_open_ library for reading from and writing to remote locations.
