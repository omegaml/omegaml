Getting started
===============

Loading omega|ml
----------------

Start by loading omega|ml.

.. code:: python

   import omegaml as om
   
Once loaded :code:`om` provides 3 environments that are immediately usable:

* :code:`om.datasets` - the omega|ml database for Python and Pandas objects
* :code:`om.models` - the omega|ml database for models
* :code:`om.runtime` - the omega|ml remote execution environment 


Storing and retrieving data
---------------------------

:code:`om.datasets.` provides two simple APIs to store and retrieve data:

* :code:`om.datasets.put(object, 'name')`
* :code:`om.datasets.get('name')`

Native Python objects
+++++++++++++++++++++

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

Pandas DataFrames
+++++++++++++++++

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
    
Querying Dataframes
///////////////////

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

Large, Out of Core-sized DataFrames
+++++++++++++++++++++++++++++++++++

Using lazy evaluation we can get back a proxy DataFrame, an :code:`MDataFrame`, 
which provides many of the features of a Pandas DataFrame including :code:`.loc` 
indexing and slicing, column projection and aggregation. All of these 
operations, however, are executed by the database and thus support out-of-core
sized DataFrames, that is DataFrames of arbitrary size.                
