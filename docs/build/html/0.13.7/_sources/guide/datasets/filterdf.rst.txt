Filtering Data
==============

Query filtering
---------------

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
* :code:`gt` greator than
* :code:`gte` greater or equal
* :code:`lt` less than
* :code:`lte` less or equal
* :code:`between` between two values, specify :code:`value` as a 2-tuple
* :code:`contains` contains a value, specify :code:`value` as a sequence
* :code:`startswith` starts with a string
* :code:`endswith` ends with a string
* :code:`isnull` is a null value, specify :code:`value` as a boolean

In general :code:`get` returns a Pandas :code:`DataFrame`. See the Pandas
documentation for ways to work with DataFrames.

However, unlike Pandas omega|ml provides methods to work with data that is
larger than memory. This is covered in the next section.

