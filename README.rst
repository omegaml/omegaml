OmegaML
=======

OmegaML is an integrated cloud runtime environment for scikit-learn models.
It supports both training (fit) and prediction of models both of which can
be run remotely based on data previously loaded into the OmegaML datastore.

.. code:: python

   Omega().runtime.models('mymodel').fit(X, Y)
   Omega().runtime.models('mymodel').predict(X)

Features
--------

* store Pandas dataframes, numpy arrays or pure python dict, list, tuples
* store scikit-learn Pipeline and Estimators
* execute fit() and predict() methods locally or in a remote container
* train models locally and deploy for online prediction with one simple command  
* automated model versioning

Why OmegaML?
------------

Training and deploying scikit-learn models into the cloud is a cumbersome 
effort: It requires some form of an online storage to store data and models once they
are trained, and an execution environment to run training and prediction processes.

Enter OmegaML:

.. code:: python

   # assume we have data in appropriate format and we are happy
   # with the models' performance
   myclf = LogisticRegression()
   myclf.fit(X, Y)
   
   # deploy
   om = Omega()
   om.models.put(myclf, 'myclf')
   
   # ready to rock
   result = om.runtime.models('myclf').predict(X)
   y = result.get()
   
Even online trainining is a breeze:

.. code:: python

   # assume we have data in appropriate format and we are happy
   # with the models' performance
   myclf = LogisticRegression()
   
   # deploy model and data
   om = Omega()
   om.models.put(myclf, 'myclf')
   om.datasets.put(mydataX, 'dataX')
   om.datasets.put(mydataY, 'dataY')
   
   # fit model online
   result = om.runtime.models('myclf').fit('dataX', 'dataY')
   
   # ready to rock
   result = om.runtime.models('myclf').predict('dataX')
   y = result.get()
   
 
How it works
------------

OmegaML consists of the following core components:

* Omega - the client interface
* OmegaStore - the online store, backed by MongoDB
* OmegaRuntime - the proxy to the remote runtime, backed by RabbitMQ and Celery

The `Omega` client interface is the main entry point for any client. At a
minimum, the client requires Celery and ampq libraries and may optionally 
have scikit-learn and pandas installed. If the client does not have scikit-learn 
and pandas installed, Omega will transparently convert input and output data 
into pure python format or return a file-like object to retrieve the data into
a local file.

`OmegaStore` is the storage-workhorse. It offers only the obvious methods
and then gets out of the user's way to do its job: `put(), get(), list(), drop()`. 
That's it. 

`OmegaRuntime` is a proxy to the remote execution container and only offers
one method: `models()`. This instructs the remote container to retrieve a
model from the store and returns a model proxy object. This can then be
used to run any of the model's methods on it, such as `fit(), predict()`. 

The call to a runtime model method such as `predict()` is executed asynchronously
and retrieves a promise-like object. To retrieve the actual result, simply call the
result's `get()` method:

.. code:: python

   result = Omega.runtime.models('mymodel').predict(X)
   y = result.get()
   
     
*How to store data*::

   Omega.datasets.put(object, 'name')
   
Here, `object` can by Pandas dataframe, a numpy array, or a python
list, dict or tuple. Omega will transparently convert the data into its 
appropriate storage format and transmit it to the store. Metadata will 
automatically be generated so that the data can be easily retrieved later on.    
   
*How to retrieve data*::

   Omega.datasets.get('name')

*How to work with models locally*::

   # create models as usual
   mymodel = LinearRegression()
   mymodel.fit(X)
   ...
   
   # store remotely
   om = Omega()
   om.models.store(mymodel, 'mymodel')
   
   # execute remotely
   om = Omega()
   X = data frame, array, numpy array # as supported by the scikit-learn estimator
   om.runtime.models('mymodel').predict(X)
   
   # fit remotely
   om = Omega()
   X = feature vector
   Y = target array/vector # as supported by the scikit-learn estimator
   # -- store data in Omega
   om.datasets.put(X, 'dataX')
   om.datasets.put(Y, 'dataY')
   # -- fit a model using data stored already
   om.runtime.models('mymodel').fit('dataX', 'dataY')
   # -- we can also upload data implicitly, which only stores the
   #    data temporarily in Omega
   om.runtime.models('mymodel').fit(X, Y)
   