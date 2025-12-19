Storing and retrieving data
===========================

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

Pandas DataFrames, Series
+++++++++++++++++++++++++

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
    
