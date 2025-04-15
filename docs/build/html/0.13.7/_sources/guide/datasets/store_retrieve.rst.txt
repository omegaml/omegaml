Storing and retrieving data
===========================

:code:`om.datasets.` provides two simple APIs to store and retrieve data:

* :code:`om.datasets.put(object, 'name')`
* :code:`om.datasets.get('name')`

Native Python objects
---------------------

Any Python native :code:`list` or :code:`dict` object can be stored and
read back directly:

.. code::

    myvar = ['data']
    om.datasets.put(myvar, 'foo')
    data = om.datasets.get('foo')
    =>
    [['data']]

Note the result is now a list of the objects stored. This is because any
object is stored as a document in a monogodb collection. What you get back
is a list of all the documents in the collection. By default :code:`put` will
append an existing collection with new documents.

.. code::

    om.datasets.put(myvar, 'foo')
    om.datasets.put(myvar, 'foo')
    data = om.datasets.get('foo')
    =>
    [['data'], ['data'], ['data']]

To replace all documents in a collection use the :code:`append=False` kwarg.

.. code::

    myvar = ['data']
    om.datasets.put(myvar, 'foo', append=False)
    data = om.datasets.get('foo')
    =>
    [['data']]

Pandas DataFrames, Series
-------------------------

Pandas Dataframes are stored in much the same way. Note however that DataFrames
provide additional support on querying, as shown in the next section

.. code::

    import pandas as pd
    df = pd.DataFrame({'x': range(10)})
    om.datasets.put(df, 'foodf', append=False)
    om.datasets.get('foodf')
    =>
       x
    0  0
    1  1
    2  2
    3  3
    4  4
    5  5
    6  6
    7  7
    8  8
    9  9


External Sources
----------------

Any Python tools can be used to retrieve data from external sources and ingest into omega|ml datasets.
For example, you could use the Pandas' library :code:`pd.read_csv` to read a remote csv file and insert
it into :code:`om.datasets`:

.. code:: python

    # small datasets
    # -- note pandas will read all of the dataset into memory, limiting the size of the dataset
    df = pd.read_csv('http://example.com/data.csv')
    om.datasets.put(df, 'example_data')

    # larger then memory datasets
    # this will load the dataset in chunks, limitting the amount of memory pandas uses
    for chunk_df in pd.read_csv('http://example.com/data.csv', chunksize=1000):
        om.datasets.put(chunk_df, 'example_data')

Alternatively, omega|ml provides a convenience function, `om.datasets.read_csv` to ingest data
from a wide range sources (e.g. S3, HTTPS, SFTP, HDFS, Azure Blob, GCS, etc.).

.. code:: pyton

    # retrieve the data and store in the example_data dataset
    om.datasets.read_csv('http://example.com/data.csv', 'example_data')


Similarly, :code:`om.datasets.to_csv` supports writing directly to remote locations:

.. code:: python

    om.datasets.to_csv('example_data', 's3://my_bucket/example_data.csv')

Accessing DBMS via SQL
----------------------

If the data resides in an SQL database, `om.datasets` can store the connection to the database:

.. code::

    # one time, e.g. one person in the team can set this up
    mydb_cxs = f'mysql://user:pass@dbhost/db'
    om.datasets.put(mydb_cxs, 'mysqldb')

Once the connection is stored like this, dataframes can be stored and retrieved using the
connection without knowing the connection string:

.. code::

    # store
    df = pd.DataFrame({'x': range(100)})
    om.datasets.put(df, 'mysqldb')

    # retrieve
    df = om.datasets.get('mysqldb')

Note by default the dataset name is used as the table name, prefixed by the bucket name (defaults to :code:`omegaml`).
In the previous example, the actual table is the :code:`omegaml_mysqldb` table.

To change the table name, specify the :code:`table=` keyword when storing the connection. In the following example,
the actual table is :code:`omegaml_mytable`,

.. code::

    # store data in a given table
    mydb_cxs = f'mysql://user:pass@dbhost/db'
    om.datasets.put(mydb_cxs, 'mysql-table', table='mytable')

To specify an existing table, without the bucket name, prefix the table name with a colon, as follows. This will
store the data in table :code:`mytable`.

.. code::

    # store data in a given table
    mydb_cxs = f'mysql://user:pass@dbhost/db'
    om.datasets.put(mydb_cxs, 'mysql-table', table=':mytable')

To specify a query to be run on retrieving the dataset, specify the :code:`sql=` keyword:

.. code::

    # store data in a given table
    mydb_cxs = f'mysql://user:pass@dbhost/db'
    om.datasets.put(mydb_cxs, 'mysql-table', table=':mytable', sql="select * from mytable")

Further possibilites include specifying variables for the connection string (e.g. userid, password) or
the sql statement. Details see :py:class:`omegaml.backends.sqlalchemy.SQLAlchemyBackend`


Storing and retrieving files
----------------------------

Files can be stored and retrieved natively in several ways :

1. Use a Python file-like object as input and output:

    .. code::

        # .put() will call file_in.read()
        with open('myfile.bin', 'rb') as file_in:
            om.datasets.put(file_in, 'myfile.bin')

        # .get() returns a file-like object
        data = om.datasets.get('myfile.bin').read()


2. Directly use a local path:

    .. code::

        om.datasets.put('myfile.bin', 'testfile')
        om.datasets.get('testfile', local='myfile.bin')








