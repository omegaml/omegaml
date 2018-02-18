Filtering Data
==============

Introduction
++++++++++++

The :code:`.get` method when operating on a Pandas DataFrame provides 
keyword-style filtering and an optional lazy evaluation mode. Filters are 
applied remotely inside the database and thus perform much faster than if 
filtered in the returned dataframe. 

.. code::

   om.datasets.get('foodf', x__gt=5)
   =>
       x
    6  6
    7  7
    8  8
    9  9
    
The filter syntax is :code:`<column>__<operator>=<value>`, where the operator
is one of the following:

* :code:`eq` compare equal (this is also the default, when using the short form, i.e.
  :code:`<column>=<value>`
* :code:`gt` greater than
* :code:`lt` less than
* :code:`ge` greator or equal
* :code:`le` less or equal
* :code:`between` between two values, specify :code:`value` as a 2-tuple
* :code:`contains` contains a value, specify :code:`value` as a sequence
* :code:`startswith` starts with a string
* :code:`endswith` ends with a string
* :code:`isnull` is a null value, specify :code:`value` as a boolean

In general :code:`get` returns a Pandas :code:`DataFrame`. See the Pandas
documentation for ways to work with DataFrames.

However, unlike Pandas omega|ml provides methods to work with data that is
larger than memory. This is covered in the next section.  

Large, Out of Core-sized DataFrames
+++++++++++++++++++++++++++++++++++

Using lazy evaluation we can get back a proxy DataFrame, an :code:`MDataFrame`, 
which provides many of the features of a Pandas DataFrame including :code:`.loc` 
indexing and slicing, column projection and aggregation. All of these 
operations, however, are executed by the database and thus support out-of-core
sized DataFrames, that is DataFrames of arbitrary size.                

.. code::
   
   om.datasets.get('dfx', lazy=True)
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

Column projection
-----------------

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
  
Row projection
--------------

Specify the index of the rows to be accessed:

.. code::

   om.datasets.get('dfx', lazy=True).loc[2:5].value
   => 
       x  y
    2  2  2
    3  3  3
    4  4  4
    5  5  5
    
Filter data
-----------

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
    
    
Permanently setting a filter
----------------------------

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
    
Sorting
-------

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
--------------------------

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
------------

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


Geo proximity filtering
-----------------------

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
    
Understanding the actual MongoDB query
--------------------------------------

Sometimes it is useful to know the actual MongoDB query that is executed,
e.g. for debugging or performance tuning purpose. :code:`.inspect()` returns
the actual query that will be executed on accessing the :code:`.value`: 
property.

.. code::

   om.datasets.get('dfx', lazy=True).query(x__gt=2, x__lt=5).inspect()
   =>
   {'explain': 'specify explain=True',
    'projection': ['x', 'y'],
    'query': {'$and': [{'x': {'$lt': 5}}, {'x': {'$gt': 2}}]}}
    

Explaining the access path
-------------------------- 

To understand the full access path and indicies used by MongoDB, use the
:code:`explain=True` keyword.

.. code::

   om.datasets.get('dfx', lazy=True).query(x__gt=2, x__lt=5).inspect(explain=True)
   =>
   {'explain': {'executionStats': {'allPlansExecution': [],
   'executionStages': {'advanced': 4,
    'executionTimeMillisEstimate': 0,
    'inputStage': {'advanced': 4,
     'direction': 'forward',
     'docsExamined': 1100,
     'executionTimeMillisEstimate': 0,
     'filter': {'$and': [{'x': {'$lt': 5}}, {'x': {'$gt': 2}}]},
     'invalidates': 0,
     'isEOF': 1,
     'nReturned': 4,
     'needTime': 1097,
     'needYield': 0,
     'restoreState': 8,
     'saveState': 8,
     'stage': 'COLLSCAN',
     'works': 1102},
    'invalidates': 0,
    'isEOF': 1,
    'nReturned': 4,
    'needTime': 1097,
    'needYield': 0,
    'restoreState': 8,
    'saveState': 8,
    'stage': 'PROJECTION',
    'transformBy': {'_idx#0_0': 1, 'x': 1, 'y': 1},
    'works': 1102},
   'executionSuccess': True,
   'executionTimeMillis': 1,
   'nReturned': 4,
   'totalDocsExamined': 1100,
   'totalKeysExamined': 0},
  'ok': 1.0,
  'queryPlanner': {'indexFilterSet': False,
   'namespace': 'testing3.omegaml.data_.dfx.datastore',
   'parsedQuery': {'$and': [{'x': {'$lt': 5}}, {'x': {'$gt': 2}}]},
   'plannerVersion': 1,
   'rejectedPlans': [],
   'winningPlan': {'inputStage': {'direction': 'forward',
     'filter': {'$and': [{'x': {'$lt': 5}}, {'x': {'$gt': 2}}]},
     'stage': 'COLLSCAN'},
    'stage': 'PROJECTION',
    'transformBy': {'_idx#0_0': 1, 'x': 1, 'y': 1}}},
  'serverInfo': {'gitVersion': '22ec9e93b40c85fc7cae7d56e7d6a02fd811088c',
   'host': 'c24ade3fa980',
   'port': 27017,
   'version': '3.2.9'}},
 'projection': ['x', 'y'],
 'query': {'$and': [{'x': {'$lt': 5}}, {'x': {'$gt': 2}}]}}
 
 

