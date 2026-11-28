Introduction
------------


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

Selection
---------

Column projection
+++++++++++++++++

Specify the list of columns to be accessed:

.. code::

   om.datasets.get('dfx', lazy=True)[['x', 'y']].head(5).value
   =>
       x  y
    0  0  0
    1  1  1
    2  2  2
    3  3  3
    4  4  4

Masked-style selection
++++++++++++++++++++++

As with Pandas DataFrames, omega|ml MDataFrames can be subset using filter masks:

.. code::

   mdf = om.datasets.getl('dfx')
   flt = (mdf['x'] > 2) & (mdf['x] < 4)
   mdf[flt].value
   =>
       x  y
    3  3  3

.. note::

    MDataFrame masks are not series of True/False as they are in Pandas. Instead a
    MDataFrame filter mask translates into a query filter that is applied on accessing
    the :code:`.value` property. Consider MDataFrame a syntactical convenience that makes
    it easy to transform code for a Pandas DataFrame to an MDataFrame.


Index-Row selection
+++++++++++++++++++

Specify the index of the rows to be accessed:

.. code::

   # numeric index
   om.datasets.get('dfx', lazy=True).loc[2:5].value
   =>
       x  y
    2  2  2
    3  3  3
    4  4  4
    5  5  5

   # alphanumeric index
   om.datasets.get('dfx', lazy=True).loc['abc'].value
   =>
         x  y
    abc  2  2


Numeric row selection
+++++++++++++++++++++

Specify the numeric row id. Note this requires that the dataset was created with a continuous row id
(automatically created when using :code:`datasets.put`)

.. code::

   # numeric index
   om.datasets.get('dfx', lazy=True).iloc[2:5].value
   =>
       x  y
    2  2  2
    3  3  3
    4  4  4
    5  5  5

.. note::

    The :code:`.iloc` accessor is also used by scikit-learn's KFold and grid search features. Since
    MDataFrame's are very efficiently serializable (only specifications are serialized, not actual data)
    this feature makes MDataFrames an attractive choice for gridsearch in a compute cluster. Actually
    MDataFrame instances can be used directly with gridsearch, whereas for example Dask's DataFrame implementation
    cannot.


Filtering data
--------------

Filtering works the same on an MDataFrame as with the eager :code:`get`
method, by specifying the filter as the keyword arguments:

.. code::

   om.datasets.get('foodf', x__gt=5, lazy=True).value
   =>
       x
    6  6
    7  7
    8  8
    9  9

Geo proximity filtering
+++++++++++++++++++++++

If you have licensed the geo location proximity extensions,
:code:`MDataFrame` supports filtering on geodesic proximity by specifying
the :code:`__near` operator and a pair of (lat, lon) coordinates. The result
is the list of matching locations sorted by distance from the given coordinates.

.. code::

    om.datasets.getl('geosample',
    location__near=dict(location=(7.4474468, 46.9479739))).value['place']
    =>
    2        Bern
    3      Zurich
    1      Geneva
    0    New York
    Name: place, dtype: object


Permanently setting a filter
++++++++++++++++++++++++++++

Note that the :code:`query` method returns a new :code:`MDataFrame` instance
with the filter applied.  To set a permanent filter for any subsequent
operations on a specific :code:`MDataFrame` instance, use the
:code:`query_inplace` method:

.. code::

   mdf = om.datasets.get('dfx', lazy=True)
   id(mdf)
   => 140341971534792

   # mdf2 is a new object
   mdf2 = mdf.query(x__gt=2, x__lt=5)
   id(mdf2)
   => 140341971587648

   # note how mdf3 is the same object as mdf above
   mdf3 = mdf.query_inplace(x__gt=2, x__lt=5))
   id(mdf3)
   => 140341971523792

   mdf = om.datasets.get('dfx', lazy=True).query_inplace(x__gt=2, x__lt=5)
   mdf.value
   =>
       x  y
    3  3  3
    4  4  4
    3  3  3
    4  4  4

.. note::

   A new :code:`MDataFrame` object returned by the :code:`query` method
   does *not* create a new collection in MongoDB. That is, the new instance
   operates on the same data. The only difference is that one new instance
   has a permanent filter applied and any subsequent operations on it will
   work on the subset of the data returned by the filter.

Ordering operations
-------------------

Sorting
+++++++

Sorting works by specifying the sort columns. Use :code:`-` and :code:`+`
before any column name to specify the sort order as descending or ascending,
respectively (ascending is the default).

.. code::

   om.datasets.get('dfx', lazy=True).sort(['-x', '+y']).head(5).value
   =>
         x    y
    999  999  999
    998  998  998
    997  997  997
    996  996  996
    995  995  995


Limiting and skipping rows
++++++++++++++++++++++++++

The :code:`head(n)` and :code:`skip(n)` methods return and skip the top _n_
rows, respectively:

.. code::

   om.datasets.get('dfx', lazy=True).skip(5).head(3).value
   =>
      x  y
   5  5  5
   6  6  6
   7  7  7

Merging data
++++++++++++

Merging supports left, inner and right joins of two :code:`MDataFrame`.
The result is stored as a collection in MongoDB and all merge operations
are executed by MongoDB. The result of the :code:`merge()` method is a new
:code:`MDataFrame` on the result

.. code::

    import pandas as pd
    # create two dataframes and store in omega|ml
    dfl = pd.DataFrame({'x': range(3)})
    dfr = pd.DataFrame({'x': range(3), 'y': range(3)})
    om.datasets.put(dfl, 'dfxl', append=False)
    om.datasets.put(dfr, 'dfxr', append=False)
    # merge the dataframes
    mdfl = om.datasets.get('dfxl', lazy=True)
    mdfr = om.datasets.get('dfxr', lazy=True)
    mdfl.merge(mdfr, on='x').value
    =>
       x  y
    0  0  0
    1  1  1
    2  2  2


Aggregation
-----------

Much like a Pandas DataFrame, :code:`MDataFrame` supports aggregation. All
aggregation operations are executed by MongoDB.

Statistics
++++++++++

The following statistics can be computed on pairs of numeric columns of a :code:`MDataFrame` and on :code:`MSeries`:

* :code:`correlation` - returns the pearson correlation matrix
* :code:`covariance` - returns the covariance matrix

.. code::

    mdf = om.datasets.getl('foo')
    mdf['x', 'y].correlation().value
    mdf['x', 'y].covariance().value


The following statisics can be computed on all numeric columns:

* :code:`mean`
* :code:`min`
* :code:`max`
* :code:`std`
* :code:`quantile` - by defaults calculates the .5 quantile, specify a list of percentiles


.. code::

    mdf = om.datasets.getl('foo')
    mdf['x', 'y].mean()
    mdf['x', 'y].min()
    ...

Grouping data
+++++++++++++

.. code::

    mdf = om.datasets.getl('dfx')
    mdf.groupby('x').x.mean().head(5)
    =>
         x_mean
    x
    0     0.0
    1     1.0
    2     2.0
    3     3.0
    4     4.0

Multiple aggregations can be applied at once by the :code:`agg()` method:

.. code::

    mdf = om.datasets.getl('dfx')
    print(mdf.groupby('x').agg(dict(x='sum', y='mean')).head(5))

The following aggregations are currently supported:

* :code:`sum` - sum
* :code:`mean` or :code:`avg` - mean
* :code:`max` - the max value in the group
* :code:`min` - the min value in the group
* :code:`std` - standard deviation in the sample
* :code:`first` - the first in the group
* :code:`last` - the last in the group


