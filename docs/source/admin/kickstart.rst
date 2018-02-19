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

The following setup is provided in :code:`docker-compose.yml` with all
services directed via a nginx reverse proxy (the nginx service is not shown
as it is not a required component):  

.. image:: /images/deployment.jpg

* *app client* - some third party app that uses the omega|ml REST API
* *data science client* - a fully fledged data science workstation that
  directly talks to the omega|ml compute & data cluster
* *omegaweb* - the REST API and omega|ml web application
* *mysql* - the MySQL database used by omegaweb
* *rabbitmq* - the integration broker between omegaweb/compute cluster and
  data science clients/compute cluster
* *runtime* - the compute cluster, consisting of a central scheduler (runtime),
  at least 1 worker and at least 1 mongodb master. workers and mongodbs can be 
  scaled horizontally as required to meet performance requirements.
  
.. note:: 

   A single-node deployment is possible and does not require rabbitmq nor
   omegaweb/mysql. 
   
   If the runtime is Dask Distributed, zeroMQ instead of rabbitmq is used. 
   
   Both Dask Distributed and Celery Workers can be deployed to an Apache Spark 
   Master node in which case a Spark cluster is presumed; details see below. 
  

Installation
------------

.. _kompose.io: http://kompose.io/getting-started/

We provide the omega|ml Dockerfile and docker-compose configuration to
run omega|ml on a single node, a docker swarm cluster or kubernetes. This
guide assumes a docker-compose single-node deployment.

.. note::

   To go from docker-compose to kubernetes, consider adopting 
   the kubernetes deployments from the omega|ml :code:`docker-compose.yml`
   file using kompose.io_ 
   
1. make sure you have the sources to build the omega|ml docker image,   
   typically provided as a release file, e.g. :code:`omegaml-release-0.1.zip`
   
2. build the docker image::

   $ mkdir -p /path/to/omegaml-release-0.1.zip
   $ cd /path/to/release/docker-staging
   $ unzip omegaml-release-<version>.zip
   $ docker build -t omega|ml .
   
3. run docker-compose::

   $ docker-compose up
   
   This will start a series of docker containers, the microservices needed
   to run omega|ml:
   
   * omegaml - the omega|ml web server 
   * worker - the omega|ml compute cluster
   * mongodb - the omega|ml data cluster
   * mysql - the webserver's database
   * rabbitmq - the communication bus between web server, worker and clients 
   * nginx - the front-end proxy to expose omegaml, rabbitmq and mongodb
|   

   .. note::
   
     nginx is not technically required. It is included as a demonstration
     of one approach to exposing rabbitmq and mongodb to data sicence clients 
     hosted outside of the omega|ml compute & data cluster. 
     
     Exposure of rabbitmq and mongodb is not a pre-requiste to using omega|ml
     as data scientists can work on the cluster directly using the notebook
     service.   
     
4. secure mongodb::

     $ cat scripts/mongoinit.js | docker exec -i omegaml_mongodb_1 mongo
     MongoDB shell version v3.4.5
     connecting to: mongodb://127.0.0.1:27017
     MongoDB server version: 3.4.5
     { "ok" : 1 }
     bye

   
   .. note:: 
   
      You can verify this was successful by running the same command again. 
      It will respond with code 13, *unauthorized* 
   
5. initialize & secure omegaweb

   .. code:: 

      $ docker exec -i build_omegaml_1 python manage.py loaddata landingpage.json
      Installed 1 object(s) from 1 fixture(s)
      
      $ docker exec -ti build_omegaml_1 python manage.py createsuperuser
        Username (leave blank to use 'root'): admin
        Email address: admin@example.com
        Password: 
        Password (again): 
        Superuser created successfully.

      
   You will need the admin user to access the admin UI at 
   http://localhost:5000/admin/
|
   
6. set data science client configuration (optional)

   Data science clients need direct access to rabbitmq and mongodb. To this
   end omega|ml needs to know the externally accessible host name so that it
   can provide to clients the client-specific, password-protected URLs 
   (see `Client Configuration`_).
   
   The parameters to be set are in the admin UI at 
   http://localhost:5000/admin/constance/config:
   
   * :code:`BROKER_URL` - this is the rabbitmq broker used by the Celery cluster.
     Set as :code:`ampq://public-omegaml-hostname:port/<vhost>/`.
     Set vhost depending on your rabbitmq configuration. By default the vhost 
     is an empty string
   * :code:`MONGO_HOST` - set as :code:`public-mongodb-hostname:port` 
|

   .. note::
   
      If you run the omega|ml docker image using docker-compose locally, set
      :code:`BROKER_URL=ampq://localhost//` and :code:`MONGO_HOST=localhost`.
      The docker-compose configuration already exposes the rabbitmq and mongodb 
      containers at their default ports, served through nginx.
      
   .. warning::
   
      The default configuration does not provide network-level security 
      as it exposes omegaweb, mongodb and rabbitmq over their native, 
      non-encrypted tcp transports and thus is not fit for enterprise 
      production deployment.
      
      However, mongodb, mysql and omegaweb as well as tasks executed on 
      the Celery cluster are protected via userid/password and userid/apikey 
      authentication thus there is no unauthorized exposure of data or models 
      even in the default configuration.         
   
   
7. access dashboard and Jupyter notebook

   .. code::

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

   1. open http://public-omegaml-hostname:port
   2. sign up
   3. on your account profile get the userid and apikey
   
3. Create a configuration file:: 

   $ python -m omegacli init --userid <userid> --apikey <key> --url http://omegamlhost:port
   
   This will create the :code:`$HOME/.omegaml/config.yml` file set up 
   to work with your omega|ml account created above.  
   
3. Launch Jupyter notebook

   1. create a notebook
   2. load omegaml
   
      .. code::
   
        import omegaml as om
        om.datasets.list() 


Application client
++++++++++++++++++

1. Create an account with omegaml::

   1. open http://omegamlhost:port
   2. sign up
   3. on your account profile get the userid and apikey

2. On every request to omegaml's REST API, provide the userid and apikey as 
   the :code:`Authorization` header, as follows
   
   
   .. code::
    
      Authorization: userid:apikey
 