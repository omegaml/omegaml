Getting Started with omega|ml
============================

omega|ml is the data science integration platform that consists of a compute 
cluster, a highly scalable distributed NoSQL database and a web app providing
a dashboard and REST API. omega|ml enables data scientists to offload all the 
heavy-lifting involved with machine learning and analytics
workflows, while enabling third-party apps to use machine learning models
in production. 

Deployment layout
-----------------

.. image:: /images/deployment.jpg

* *app client* - some third party app that uses the omega|ml REST API
* *data science client* - a fully fledged data science workstation that
  directly talks to the omega|ml compute & data cluster
* *omegaweb* - the REST API and omega|ml web application
* *mysql* - the MySQL database used by omegaweb
* *rabbitmq* - the integration broker between omegaweb/compute cluster and
  data science clients/compute cluster
* *runtime* - the compute cluster, consisting of a central scheduler (runtime),
  at least 1 and at least 1 mongodb master. workers and mongodbs can be 
  scaled horizontally as required to meet performance requirements.
  
.. note:: 

   A single-node deployment is possible and does not require rabbitmq nor
   omegaweb/mysql. Similarly if the runtime is a Dask Distributed cluster 
   zeroMQ instead of rabbitmq is used. Workers can be deployed to
   a Apache Spark Master node in which case a Spark cluster is presumed;
   details see below. 
  

Installation
------------

.. _kompose.io: http://kompose.io/getting-started/

We provide the omega|ml Dockerfile and docker-compose configuration to
run omega|ml on a single node, a docker swarm cluster or kubernetes. This
guide assumes a docker-compose single-node deployment.

.. note::

   To go from docker-compose to kubernetes, you may create our kubernetes
   deployment using kompose.io_ 
   
1. make sure you have the sources to build the omega|ml docker image
   (or a source to acquire the docker image directly)
   
2. build the docker image::

   $ mkdir -p /path/to/release/docker-staging
   $ cd /path/to/release/docker-staging
   $ unzip omegaml-release-<version>.zip
   $ docker build -t omega|ml .
   
3. run docker-compose::

   $ docker-compose up
   
4. access dashboard and Jupyter notebook::

   # dashboard 
   open http://localhost:5000/
   
   # notebook
   open http://localhost:8888/
   

Client Configuration
--------------------

omega|ml supports two types of clients:

1. Data Science workstation - a local workstation / PC / laptop with a 
   full-scale data science setup, ready for a Data Scientist to work locally.
   When ready she will deploy data and models onto the runtime (the omega|ml 
   compute and data cluster), run models and jobs on the cluster or provide
   datasets for access by her colleagues. This configuration requires a
   local installation of omegaml, including machine learning libraries and
   client-side distribution components.
   
2. Application clients - some third-party application that access omega|ml
   datasets, models or jobs using omegaml's REST API. This configuration 
   has no specific requirements other than access to the REST API and the
   ability to send and receive JSON documents via HTTP.
    

Data Science workstation
++++++++++++++++++++++++

1. Setup a conda environment including omegaml::

   $ conda create -n myomegaml python=3.6
   $ source activate myomega|ml
   $ conda install --file conda-requirements.txt
   $ pip install -r requirements.txt
   $ pip install omegaml.whl
   
2. Create an account with omegaml::

   1. open http://omegamlhost:port
   2. sign up
   3. on your account profile get the userid and apikey
   
3. Create a configuration file:: 

   $ python -m omegacli init --userid <userid> --apikey <key> --url http://omegamlhost:port
   
   This will create the $HOME/.omegaml/config.yml file set up for omega|ml
   to work with your omega|ml account created above.  
   
3. Launch Jupyter notebook

   1. create a notebook
   2. load omegaml::
   
      import omegaml as om
      om.datasets.list() 


Application client
++++++++++++++++++

1. Create an account with omegaml::

   1. open http://omegamlhost:port
   2. sign up
   3. on your account profile get the userid and apikey

2. On the request to omegaml's REST API, provide the userid and apikey as 
   the :code:`Authorization` header follows::
   
   Authorization: userid:apikey
 