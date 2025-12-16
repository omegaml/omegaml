Debugging
---------

Understanding the actual MongoDB query
++++++++++++++++++++++++++++++++++++++

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
++++++++++++++++++++++++++

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


