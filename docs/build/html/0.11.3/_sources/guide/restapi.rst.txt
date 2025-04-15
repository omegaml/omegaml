REST API
========

The REST API provides a direct interface to models and datasets from any
connected client. Unlike the Python API, the client does not need access
to either MongoDB or RabbitMQ to make use of omegaml, nor does the client
need to use the Python language. Use the REST API to interface from any
third-party system to omegaml.


API Reference
-------------

The API reference is accessible online from your omega|ml instance at:

* :code:`/api/doc/v1`- Swagger UI
* :code:`/api/doc/v1/specs/swagger.json` - the Swagger specs (JSON)
* :code:`/api/redoc` - ReDoc UI, based on Swagger specs


API Semantics
-------------

The omega|ml REST API resources are all of the form 
:code:`/api/version/resource-name/resource-key/?param=value`.

The valid resource names are:

* dataset - provides access to data 
* model - provides access to models
* job - provides access to jobs *Enterprise Edition*
* config - provides access to the user-specific omega|ml configuration *Enterprise Edition*

The resource-key and query parameters are optional. If a resource-key
is not provided, a list of existing resources is returned. If a resource-key
is provided the API will look up the respective specific resource for this
key and return its content.

Note that the dataset and job resources will return dataset and job contents,
respectively. The model resource will only provide meta data, but not the
actual contents of the model.  

All resources support a set of HTTP GET, PUT, POST or DELETE methods.

* successful GET => HTTP 200 OK
* successful POST => HTTP 201 created
* successful PUT => HTTP 202 accepted

*Enterprise Edition*

* error due to bad input parameters => HTTP 400 Bad Request
* error due to authentication => HTTP 401 Unauthorized
* error due to wrong authorization => HTTP 403 Forbidden
* error due to non existing resource => HTTP 404 Not found
* error due to not allowed method => HTTP 405 Method not allowed
* severe server errors => HTTP 500 Internal Server error 


Setting up authorization
------------------------

*Enterprise Edition*

From your omega|ml portal, get the userid and api key.

.. code::

    from omegacli.auth import OmegaRestApiAuth
    auth = OmegaRestApiAuth(userid, apikey) 
    
 
Working with data
-----------------


Listing datasets
++++++++++++++++

.. code::

   resp = requests.get('http://host:port/api/v1/dataset/', auth=auth)
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

    resp = requests.get('http://host:port/api/v1/dataset/sample', auth=auth)
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
    requests.put('http://host:port/api/v1/dataset/sample/', auth=auth,
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
     'created': '2016-01-16 22:05:06.192000',
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
   

Working with jobs
-----------------

*Enterprise Edition*

The jobs api supports creating, executing and status-checking jobs on 
the cluster. 

.. warning:: 

    Creating jobs via the API assumes that the user creating the job 
    is trusted. Any code can be inserted and could potentially compromise
    your cluster.      
    
    
Creating a job
++++++++++++++

.. code::
    
    data = {
        'code': "print('hello')",        
    }
    resp = requests.post('http://localhost:8001/api/v1/job/testjob/',
                         json=data, auth=auth)
    resp.json()
    => 
    {u'job_runs': [], u'job_results': {}, 
    u'name': u'testjob.ipynb', 
    u'created': u'2016-02-06T21:31:39.326097'}
                   
                   
Listing jobs
++++++++++++

.. code::

   resp = requests.get('http://localhost:8001/api/v1/job/',
                         auth=auth)
   resp.json()
   =>
   {u'meta': {u'previous': None, u'total_count': 1, 
              u'offset': 0, u'limit': 20, u'next': None}, 
   u'objects': [{u'job_runs': [], 
                 u'job_results': {}, u'name': u'testjob.ipynb', 
                 u'created': u'2016-02-06T21:33:49.833000'}]}

Getting information on a job
++++++++++++++++++++++++++++

.. code::

   resp = requests.get('http://localhost:8001/api/v1/job/testjob/',
                         json=data, auth=auth)
   resp.json()
   =>
   {u'content': {u'nbformat_minor': 0, u'nbformat': 4, 
    u'cells': [{u'execution_count': None, u'cell_type': 
                u'code', u'source': u"print('hello')", 
                u'outputs': [], u'metadata': {}}], 
                u'metadata': {}}, u'job_runs': [], 
                u'job_results': {}, 
                u'name': u'testjob.ipynb', 
                u'created': u'2016-02-06T21:44:59.290000'}


Running a job
+++++++++++++

.. code::

   resp = requests.post('http://localhost:8001/api/v1/job/testjob/run/',
                         auth=auth)
   resp.json()
   =>
   {u'job_runs': {u'1517953074': u'OK'}, 
    u'job_results': [u'results/testjob_1517953074.ipynb'], 
    u'name': u'testjob.ipynb', 
    u'created': u'2016-02-06T21:37:54.014000'}
   

Getting job results
+++++++++++++++++++

To get job results in iPython notebook format, use 

.. code::

      
   resp = requests.get('http://localhost:8001/api/v1/job/results/testjob_1517953074.ipynb/',
                         auth=auth)
   resp.json()
   =>
   {u'source_job': u'testjob', u'job_results': {}, 
   u'created': u'2016-02-06T21:36:06.704000', 
   u'content': {u'nbformat_minor': 0, u'nbformat': 4, 
                u'cells': [{u'execution_count': 1, u'cell_type': u'code', 
                            u'source': u"print('hello')", 
                            u'outputs': [{u'output_type': 
                                          u'stream', u'name': u'stdout', 
                                          u'text': u'hello\n'}], 
                                          u'metadata': {}}], 
                u'metadata': {}}, 
   u'job_runs': [], 
   u'name': u'results/testjob_1517952965.ipynb'}
   
   
Getting a job report
++++++++++++++++++++

To get job results in HTML format, use

.. code::

   resp = requests.get('http://localhost:8001/api/v1/job/export/testjob_1517953074.ipynb/',
                         auth=auth)
   resp.json()
   =>
   {u'content': "<html> ... </html>",
    u'name': 'testjob_1517953074.ipynb'}

