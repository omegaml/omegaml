Working with MDataFrame
=======================

A short guide

.. contents::

What is MDataFrame?
-------------------

-  ``MDataFrame`` provides a Pandas-like API to omega-ml’s analytics
   storage (backed by MongoDB). The key thing about ``MDataFrames`` is
   that they represent the *description of data and processes applied to
   the data*, but do not contain data itself. In this sense
   ``MDataFrame`` is the same for MongoDB as SQL is for a relational
   database: a query language.

-  Like Pandas ``DataFrame``, ``MDataFrame`` provides convenient
   operations for querying, subsetting, and grouping data. The key
   difference is that while Pandas must always load all data into memory
   before operating on it, ``MDataFrame`` passes operations on to the
   database. The result of such operations is typically a Pandas
   ``DataFrame``, or another ``MDataFrame``.

-  For cases where the we need more complex processing than the database
   supports, ``MDataFrame`` can run a Python function on the data in
   parallel.

-  Note that ``MDataFrame`` *is not* a drop-in replacement for Pandas
   ``DataFrame``.

Concepts
--------

-  ``MDataFrame``: reprents a columnar datastructure made of of columns
   and rows
-  ``MSeries``: represents all values in a single column

In addition there are several helpers that provide specific
functionality, e.g. for positional access, slicing and group-by
processing. We don’t specify the details of these helpers as they are
tied into the MDataFrame and MSeries API.

-  ``.value`` resolves the result of all operations, e.g. filtering,
   slicing, aggregation to a local in-memory pandas dataframe (useful
   for exploratory tasks and groupby aggregation)
-  ``.apply()`` provides in-database processing (e.g. filtering,
   slicing, aggregation)
-  ``.transform()`` provides parallel out-of-core, chunk-by-chunk
   processing (use for large datasets)

Storing data as an MDataFrame
-----------------------------

You can store any of the following objects and return them as an
MDataFrame:

-  Pandas Dataframe (and any source that Pandas supports):
   ``om.datasets.put(df, 'name')``
-  Any sql source supported by the (e.g. snowflake)
   ``om.datasets.put('connstr', 'name')``
-  CSV files from an externally hosted source (ftp, http, s3):
   ``om.datasets.put(None, 'name',uri='http://....')``
-  Any other tabular-like data that you insert into the analytics store
   (i.e. MongoDB): ``om.datasets.put(docs, 'name')``

Note in general the MDataFrame is not dependent on the original *source*
of the data, but on the format it is stored in omega-ml’s analytics
storage. As long as the data can be retrieved back and transformed to a
format Pandas can work with, MDataFrame will be able to handle it. That
said, it works easiest with tabular data of rows and columns where each
cell has some scalar value.

Getting an MDataFrame
---------------------

The following methods are equivalent, both return an instance of
``MDataFrame``

::

   mdf = om.datasets.getl('name')
   mdf = om.datasets.get('name', lazy=True)

Using any of these methods, ``mdf`` will represent the ``MDataFrame``
instance. Note that this will return immediately as no data access
happens at this time.

Executing a query
-----------------

To actually get data from a MDataFrame you need to ask for evaluation.
This will execute the query according to all operations applied so far.
The result is a standard Pandas DataFrame:

::

   mdf.value

**Note this can be a dangerous operation as it will load all the data
into memory** If the result of your query is larger than the available
memory of your process, it will fail and result in an operating-system
level out of memory condition. If you are unsure how many rows a query
will return, try using ``.count()`` first.

Persisting the result of a query
--------------------------------

To evaluate an MDataFrame without returning all data into memory, use
the ``.persist()`` method

::

   mdf.persist('name', store=om.datasets)

This is the equivalent of
``df = mdf.value; om.datasets.put(df, 'name')``, however all operations
are performed in the database, results are retrieved back to memory only
if needed, and if so in small chunks.

Slicing
-------

Like Pandas DataFrame, MDataFrame can be sliced

-  by a set of columns: ``mdf[['col1', 'col2']]`` => return a MDataFrame
   subset to col1, col2
-  by single columns ``mdf['col1']`` => return a MSeries
-  by rows ``mdf.iloc[start:end]`` => return a MDataFrame subset to rows
   with index start to end.
-  by index ``mdf.loc[label]`` => return a MDataFrame subset to columns
   with corresponding labels
-  by filter ``mdf[filter-mask]``\ => return a MDataFrame subset to the
   filter mask

Note that ``.loc, .iloc`` require the data to have been stored from a
Pandas DataFrame.

Filtering
---------

*By filter masks*

::

   flt = mdf['column'] == value  # use any operator supported by MSeries
   mdf[flt]

Filtering can be done by using a combination of
``keyword__<operator>=<value``

Aggregation and transformation
------------------------------

MDataFrame provides a powerful set of aggregations:

-  in-database or local groupby processing ``mdf.groupby``
-  in-database transformation and aggregation ``mdf.apply()``
-  out-of-core parallel processing ``mdf.transform()``

In-database transformations
---------------------------

Using ``MDataFrame.apply()`` we can apply several column-wise
transformations. Note that the function passed to apply must accept an
ApplyContext.

::

   mdf.iloc[0:1000].apply(lambda v: {
       'key'      : v['l_orderkey'],
       'comment': v['l_comment'].str.concat(' *'),
       'docs': v['l_shipinstruct'].str.usplit(' '),
       'comment_lower': v['l_shipinstruct'].str.lower(),
       'comment_substr': v['l_shipinstruct'].str.substr(1, 5),
       'week': v['l_shipdate'].dt.week,
       'year': v['l_shipdate'].dt.year,
   }, inplace=True).value

Note: Unlike a Pandas apply which executes the function for every row or
column, MDataFrame will **execute the function only once** in order to
build the database query. If you want to execute Python code row-by-row,
or group-by-group, use ``.tranform()``, see below.

Parallel transformations
------------------------

MDataFrame supports in-parallel processing of arbitrary subsets and size
of data. By default, the subset will be by row number, but any other
grouping is possible.

The following snipped will start N / chunksize tasks and process them in
parallel. Each task processes N / chunksize records. The default
chunksize is 50’000. The number of parallel jobs started by default is
CPU count - 1.

::

   def myproc(df):
       df['column'] = df['other'].apply(...)

   mdf.transform(myproc).persist('name', store=om.datasets)

More explanations:

::

   def myproc(df, i):
       # df is the subset of the ith chunk of the full data
       # it is a Pandas in-memory DataFrame, apply any Pandas function you like
       # assignment is supported
       df['column'] = df['other'].apply(...)
       ...
       # groupby is also possible
       result = df.groupby(...)...
       # either return None (or no return statement) => updated df is written to the db
       # or return a DataFrame or a Series => returned object is written to the db
       return result

   # this will start N = len(mdf) / 50'000 tasks and store the results in om.datasets
   # conceptually this is the equivalence of df = mdf.value.apply(myproc); om.datasets.put(df)
   # however using mdf.transform() will use much less memory and easily scale out of core
   mdf.transform(myproc).persist('name', store=om.datasets)

   # specify chunksize and n_jobs to influence the number of chunks and the number of parallel workers.
   # note this comes at a trade-off: many workers will take longer to complete, larger chunksizes will use more memory
   mdf.transform(myproc, chunksize=<#records>, n_jobs=#numbers).persist('name', store=om.datasets)

Customized chunking
-------------------

By default ``.transform()`` uses the size of the data (as in number of
rows) do determine the number of chunks. You can however create any
number chunks:

::

   mdf = om.datasets.getl('retail')

   def process(ldf):
       ldf['comments'] = ldf['l_comment'].str.split(' ')


   def chunker(mdf, chunksize, maxobs):
       # for each chunk yield a MDataFrame subset for each chunk
       # note: don't use .value before yielding as this would resolve the dataframe locally
       #       and potentially consume all memory.
       groups = mdf['l_returnflag'].unique().value
       for group in groups:
           for i in range(0, maxobs, chunksize):
               yield mdf.skip(i).head(chunksize).query(l_returnflag=group)

   (mdf
    .transform(process, chunkfn=chunker, n_jobs=-2)
    .persist('retail-transformed', store=om.datasets))

Lazy evaluation
---------------


Using lazy evaluation we can get back a proxy DataFrame, an :code:`MDataFrame`,
which provides many of the features of a Pandas DataFrame including :code:`.loc`
indexing and slicing, column projection and aggregation. All of these
operations, however, are executed by the database and thus support out-of-core
sized DataFrames, that is DataFrames of arbitrary size.

.. code::

   # ask for a reference to the dfx dataset with lazy evaluation
   om.datasets.get('dfx', lazy=True)
   =>
   <omegaml.mdataframe.MDataFrame at 0x7fa3e991ee48>

   # same thing, getl is convenience method that automatically specifies lazy=True
   om.datasets.getl('dfx')
   =>
   <omegaml.mdataframe.MDataFrame at 0x7fa3e991ee48>

:code:`MDataFrame` in many ways behaves like a normal dataframe, however the
evaluation of operations is _lazy_ and is executed by the database as opposed
to in-memory. This allows us to process data that is larger than memory.

In order to evaluate :code:`MDataFrame` and return an actual
:code:`pandas.DataFrame` just access the :code:`.value` property:

.. code::

   om.datasets.get('dfx', lazy=True).value
   =>
       x  y
    0  0  0
    1  1  1
    2  2  2
    3  3  3
    4  4  4

What won’t work
---------------

*MDataFrame are currently read-only. In other words, assignment, column
additions and smilar operations are not currently supported. This is not
an inherent restriction, there is just no API for it in the current
implementation. Note if updates are required, the MDataFrame plugin
mechanism provides a straight-forward way to provide such
functionality.*

Hence the following kind of operations are **not currently supported**:

::

    mdf[col] = mdf[col].apply(func)
    mdf[col] = mdf[col].map(func)
    mdf[col] = value # partial support is available, but limited to scalar values
