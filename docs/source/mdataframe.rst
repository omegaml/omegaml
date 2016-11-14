Out of core DataFrames
======================

omegaml supports working with pandas DataFrames that are larger than
available memory by leveraging mongodb as its datastore. This documents
the available features supported by omegaml's MDataFrame. 

.. note::

    omegaml takes a different approach to other frameworks like dask. While
    dask is focused on distributed processing of a compute-graph and strives
    for data-locality, omemgal's focus is on scalable data-persistence, 
    data-sharing and collaboration in teams of data scientists and 
    to provide a distributed API to micro-services that require analytical
    services but do not themselves have the required compute power. This said,
    the power of dask and omegaml can be combined.
    
Features
--------

omegaml supports efficient persistency of and distributed access to the 
following Pandas objects:

* DataFrames
* Series
* HDFStores

omegaml provides a functional API to MongoDB's aggregation and map/reduce
framework, as well as storing geocoded data with geospatial search semantics 
(e.g. near, within).

In addition omegaml supports the storage and distributed access to 

* scikit-learn models
* Apache Spark models
* Python container objects (dict, list, tuples)


Concepts
--------

* *OmegaStore* - a store is the persistence layer that mediates between 
  Python/Pandas and Mongodb. There are three types of stores: data store,
  model store and jobs (code) store. 
* *Bucket* - a bucket is a namespace within a Mongo database. All objects stored
  by omegaml reside within a bucket
* *Prefix* - the prefix is the multi/level/path prefix to an object stored 
  in a bucket. Think of this as a hierarchical file system within a bucket
* *Metadata* - omegaml manages its objects in the bucket's metadata collection

   
Access an MDataFrame
--------------------

To access an out-of-core MDataFrame you need to put some data into MongoDB:

.. code:: python

    In : import omegaml as om
         import pandas as pd
            
         df = pd.DataFrame({'x': range(10)})
         om.datasets.put(df, 'foo')

    Out: <Metadata: Metadata(kind=pandas.dfrows,name=foo, ...)
    
This stores the :code:`df` DataFrame with name :code:`foo`. We can get it
back just as quick:

.. code:: python

    In : om.datasets.get('foo')
    
    Out: 
                x
            0   0
            1   1
            2   2
            3   3
            4   4
            5   5
            6   6
            7   7
            8   8
            9   9
            
You may wonder what we just got back? It's a standard pandas DataFrame:

    In : type(om.datasets.get('foo') 
    
    Out: pandas.core.frame.DataFrame
    
This omegaml's default behavior: it returns the same data that it received.

  
       



  




 