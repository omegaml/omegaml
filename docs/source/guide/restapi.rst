REST API
========

The REST API provides a direct interface to models and datasets from any
connected client. Unlike the Python API, the client does not need access
to either MongoDB or RabbitMQ to make use of omegaml, nor does the client
need to use the Python language. Use the REST API to interface from any
third-party system to omegaml.


API Reference
-------------

The API reference is accessible online from your omegaml instance at:

* :code:`/api/doc/v1`- Swagger UI
* :code:`/api/doc/v1/specs/swagger.json` - the Swagger specs (JSON)
* :code:`/api/redoc` - ReDoc UI, based on Swagger specs


Setting up authorization
------------------------

From your omegaml portal, get the userid and api key.

.. code::

    from omegacli.auth import OmegaRestApiAuth
    auth = OmegaRestApiAuth(userid, apikey) 
    
 
Working with data
-----------------


Listing datasets
++++++++++++++++

.. code::

   resp = requests.get('http://omegaml.dokku.me/api/v1/dataset/', auth=auth)
   resp.json()
   => 
   {'meta': {'limit': 20,
  'next': None,
  'offset': 0,
  'previous': None,
  'total_count': 3},
 'objects': [{'data': {'kind': 'pandas.dfrows', 'name': 'sample'},
   'dtypes': None,
   'index': None,
   'name': None,
   'orient': None,
   'resource_uri': '/api/v1/dataset/sample/'},
  {'data': {'kind': 'pandas.dfrows', 'name': 'sample2'},
   'dtypes': None,
   'index': None,
   'name': None,
   'orient': None,
   'resource_uri': '/api/v1/dataset/sample2/'},
  {'data': {'kind': 'pandas.dfrows', 'name': 'sample99'},
   'dtypes': None,
   'index': None,
   'name': None,
   'orient': None,
   'resource_uri': '/api/v1/dataset/sample99/'}]}
   


Reading data
+++++++++++++

.. code::

    resp = requests.get('http://omegaml.dokku.me/api/v1/dataset/sample', auth=auth) 
    resp.json()
    => 
    {'data': {'x': {'0': 0,
   '1': 1,
   '10': 0,
   '11': 1,
   '12': 2,
   '13': 3,
   '14': 4,
   '15': 5,
   '16': 6,
   '17': 7,
   '18': 8,
   '19': 9,
   '2': 2,
   '20': 0,
   '21': 1,
   '22': 2,
   '23': 3,
   '24': 4,
   '25': 5,
   '26': 6,
   '27': 7,
   '28': 8,
   '29': 9,
   '3': 3,
   '4': 4,
   '5': 5,
   '6': 6,
   '7': 7,
   '8': 8,
   '9': 9}},
 'dtypes': {'x': 'int64'},
 'index': {'type': 'Int64Index',
  'values': [0,
   1,
   2,
   3,
   4,
   5,
   6,
   7,
   8,
   9,
   0,
   1,
   2,
   3,
   4,
   5,
   6,
   7,
   8,
   9,
   0,
   1,
   2,
   3,
   4,
   5,
   6,
   7,
   8,
   9]},
 'name': 'sample',
 'orient': 'dict',
 'resource_uri': '/api/v1/dataset/None/'}
 
.. note::

    To get a valid dataframe back do as follows.
    
    .. code::
    
       import pandas as pd
       df = pd.DataFrame.from_dict(resp.json().get('data'))
       df.index = index=resp.json().get('index').get('values')
       
     
    It is important to set the index to restore the correct row order. This
    is due to Python's arbitrary order of keys in the :code:`data` dict. 
    

Writing data
++++++++++++

Writing data is equally straight forward. Note this works for both new
and existing datasets. By default data is appended to an existing dataset.

.. code::

    data = {'data': {'x': {'0': 0,
       '1': 1,
       '2': 2,
       '3': 3,
       '4': 4,
       '5': 5,
       '6': 6,
       '7': 7,
       '8': 8,
       '9': 9}},
     'dtypes': {'x': 'int64'},
     'orient': 'dict',
     'index': {'type': 'Int64Index', 'values': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]},
     'name': 'sample'}
    requests.put('http://localhost:8001/api/v1/dataset/sample/', auth=auth, 
                 json=data)
    => 
    <Response [204]>

To overwrite an existing data set, use :code:`append: false`

.. code::

    data = {'data': {'x': {'0': 0,
       '1': 1,
       '2': 2,
       '3': 3,
       '4': 4,
       '5': 5,
       '6': 6,
       '7': 7,
       '8': 8,
       '9': 9}},
     'dtypes': {'x': 'int64'},
     'append': False,
     'orient': 'dict',
     'index': {'type': 'Int64Index', 'values': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]},
     'name': 'sample'}
    requests.put('http://localhost:8001/api/v1/dataset/sample/', auth=auth, 
                 json=data)
    => 
    <Response [204]>
    
    
Transform a DataFrame to API format
+++++++++++++++++++++++++++++++++++

To transform a Pandas DataFrame into the format expected by the API, use
the following code snippet.

.. code::

   def pandas_to_apidata(df, append=False):
        # TODO put logic for this into client lib
        data = {
            'append': append,
            'data': json.loads(df.to_json()),
            'dtypes': {k: str(v)
                       for k, v in iteritems(df.dtypes.to_dict())},
            'orient': 'columns',
            'index': {
                'type': type(df.index).__name__,
                # ensure type conversion to object for Py3 tastypie does
                # not recognize numpy.int64
                'values': list(df.index.astype('O').values),
            }
        }
        return data
    
    
Working with models
-------------------

Create a model
++++++++++++++

.. code::

    data = {'name': 'mymodel',
            'pipeline': [
                # step name, model class, kwargs
                ['LinearRegression', dict()],
            ]}
    requests.post('http://localhost:8001/api/v1/model/',
                     json=data,
                     auth=auth)
    => 
    <Response [201]>
    {'model': {'bucket': 'store',
     'created': '2018-01-16 22:05:06.192000',
     'kind': 'sklearn.joblib',
     'name': 'mymodel'}}

Fit a model
+++++++++++

Create some data first:

.. code::

    # a simple data frame to learn
    df = pd.DataFrame({'x': range(10)})
    df['y'] = df['x'] * 2
    datax = pandas_to_apidata(df[['x']])
    datay = pandas_to_apidata(df[['y']])

    # store data
    requests.put('http://localhost:8001/api/v1/dataset/datax/', auth=auth, 
                 data=json.dumps(datax))
    requests.put('http://localhost:8001/api/v1/dataset/datay/', auth=auth, 
                 json=datay)
    => 
    <Response [204]>
    

Then we can fit the model:

.. code::

    resp = requests.put('http://localhost:8001/api/v1/model/mymodel/fit/?datax=datax&datay=datay', auth=auth, data={}) 
    resp.json()
    =>
    {'datax': 'datax', 'datay': 'datay', 'result': 'ok'}
    
    
Subsequently, the model is ready for prediction:

.. code::

    resp = requests.get('http://localhost:8001/api/v1/model/mymodel/predict/?datax=datax', auth=auth, data={}) 
    resp.json()
    => 
    {'datax': 'datax',
     'datay': None,
     'result': [0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0]}
   
