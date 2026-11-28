Aggregation Framework
---------------------

.. _MongoDB's aggregate: https://docs.mongodb.com/manual/reference/method/db.collection.aggregate/#db.collection.aggregate

omega|ml provides a rich aggregation framework that leverages `MongoDB's aggregate`_ operator while keeping
the ease-of-use of Pandas syntax. Typical Pandas aggregation operations like group-by and descriptive statistics
have direct equivalents in omegal|ml with the same or very similar syntax, using :code:`MDataFrame.groupby`:

Standard Groupby aggregation
++++++++++++++++++++++++++++

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

Motivating example
++++++++++++++++++

If the standard operations provided in `MDataFrame.groupby` do not provide the required functionality, custom
operators or chains of operators can be easily applied using the :code:`MDataFrame.apply()` functionality. Much like
Pandas :code:`DataFrame.apply`, :code:`MDataFrame.apply` takes a callable that operates on the data:

.. code::

    # apply to all columns on a dataframe
    mdf.apply(lambda ctx: ctx * 5)

In this example, the lambda will multiply every value in the dataframe by 5. All math operators (*, +, -, /, % etc.)
are supported, as well as a number of other operations.

.. note::

    Unlike with Pandas, the callable passed to :code:`.apply()` is *not* executed on every row. Instead the
    callable is executed once during preparation of the MongoDB query. The callable receives an :code:`ApplyContext`
    which is responsible for translating requested operations to MongoDB query syntax when the dataframe is
    resolved by accessing the :code:`.value` property. Call :code:`MDataFrame.inspect()` to see the actual MongoDB
    query.

:code:`.apply()` can be called either on a :code:`MDataFrame` or on a :code:`MSeries`. Further, when called on a
MDataFrame, the operations specified are applied to all columns. When called on a MSeries or when the column is
selected from the :code:`ApplyContext`, the operations are applied only to the one column.

.. code::

    # apply to all columns on a dataframe
    mdf.apply(lambda ctx: ctx * 5)

    # apply to a column, returning a series
    mdf['x'].apply(lambda ctx: ctx * 5)

    # apply to a column, return a dataframe
    mdf.apply(lambda ctx: ctx['x'] * 5)


Math operations
+++++++++++++++

All standard Python math operators are supported, in particular:

* :code:`__mul__` (*)
* :code:`__add__` (+)
* :code:`__sub__` (-)
* :code:`__div__` (/)
* :code:`__floordiv__` (//)
* :code:`__mod__` (%)
* :code:`__pow__` (pow)
* :code:`__ceil__` (ceil)
* :code:`__floor__` (floor)
* :code:`__trunc__` (trunc)
* :code:`__abs__` (abs)
* :code:`sqrt` (math.sqrt)

Math operators can be chained. While operator priority is taken care of by the Python compiler, you should use
brackets to ensure readability and correct operations in special scenarios:

.. code::

    # while this works, it is not recommended syntax
    mdf.apply(lambda ctx: ctx * 5 + 2)

    # recommended
    mdf.apply(lambda ctx: (ctx * 5) + 2)

Datetime Operators
++++++++++++++++++

.. code::

    mdf.apply(lambda ctx: ctx['v'].dt.year)
    mdf.apply(lambda ctx: ctx['v'].dt.month)
    mdf.apply(lambda ctx: ctx['v'].dt.week)
    mdf.apply(lambda ctx: ctx['v'].dt.day)
    mdf.apply(lambda ctx: ctx['v'].dt.hour)
    mdf.apply(lambda ctx: ctx['v'].dt.minute)
    mdf.apply(lambda ctx: ctx['v'].dt.second)
    mdf.apply(lambda ctx: ctx['v'].dt.millisecond)
    mdf.apply(lambda ctx: ctx['v'].dt.dayofyear)
    mdf.apply(lambda ctx: ctx['v'].dt.dayofweek)

String Operators
++++++++++++++++

.. code::

    mdf.apply(lambda ctx: ctx['v'].str.len())
    mdf.apply(lambda ctx: ctx['v'].str.concat(['xyz']))
    mdf.apply(lambda ctx: ctx['v'].str.split(','))
    mdf.apply(lambda ctx: ctx['v'].str.upper())
    mdf.apply(lambda ctx: ctx['v'].str.lower())
    mdf.apply(lambda ctx: ctx['v'].str.substr(start, end))
    mdf.apply(lambda ctx: ctx['v'].str.isequal('string')
    mdf.apply(lambda ctx: ctx['v'].str.index('substring'))


Cached operations
+++++++++++++++++

Any :code:`apply()` call results can be cached to speed-up future queries. To do so call :code:`persist()`:

.. code::

    mdf.apply(...).persist()

Any subsequent call to the same apply operations, :code:`.value` will retrieve the results from the results
produced by :code:`persist()`. Note that :code:`persist()` returns the cache key, not the actual results.

.. note::

    Using cached operations can tremendously speed up data science work flows for complex aggregation
    queries that need to be executed repeatedly or are common in your scenario. As an example, consider
    an aggregation on a 50GB dataset that takes several minutes to compute. Using :code:`persist()` this
    calculation can be executed once and stored for subsequent and automatic retrieval by anyone on your team.

Complex operations
++++++++++++++++++

.. _MongoDB aggregation reference: https://docs.mongodb.com/manual/meta/aggregation-quick-reference/

:code:`MDataFrame.groupby` supports only few descriptive statics, namely :code:`mean(), std(), min(), max()` since
these are the MongoDB-provided operations. However using :code:`.apply()` more complex operators can be easily
created. See the `MongoDB aggregation reference`_ for details on syntax.

Multiple statistics can be calculated for the same column:

.. code::

    mdf.apply(lambda ctx: ctx.groupby('x', v=['sum', 'mean', 'std'])


Custom statistics using MongoDB syntax

.. code::

    # specify the groupby in mongo db syntax
    expr = {'$sum': '$v'}
    # add a stage
    mdf.apply(labmda ctx: ctx.groupby('x', v=expr)


Parallel execution of multiple calculations:

.. code::

    mdf.apply(lambda ctx: dict(a=ctx['v'] * 5, b=ctx['v'] / 2))


Custom projections:

.. code::

    mdf.apply(lambda ctx: ctx.project(a={'$divide': ['$v', 2]}))


Arbitrary pipeline stages:

.. code::

    # specify the stage in mongo db syntax
    stage = {
        '$<stage>': { '<$operator>' : .... }
    }
    # add a stage
    mdf.apply(labmda ctx: ctx.add(stage))


.. note::

    The callable to :code:`apply()` shall return any of the following result types:

    * :code:`None` - this is equivalent to returning the :code:`ApplyContext` passed on calling
    * :code:`ApplyContext` - the context will be used to generate the stages passed to MongoDB's :code:`aggregate()`
    * :code:`dict` - a mapping of result-column names to an ApplyContext or a valid list of stages in MongoDB-syntax
    * :code:`list` - a list of stages in MongoDB-syntax


