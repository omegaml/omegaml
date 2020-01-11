Cloud Manager
=============

The omega|ml managed service runs best in a Kubernetes (k8s) environment hosted
at a cloud provider, where

* the k8s cluster manages the allocation of work loads
* the cloud provider manages the compute and storage resources
* opsmgr works with the cluster and the cloud provider to deploy services,
  including the provision of additional nodes and the deployment or scaling
  of resources on the cluster

.. note::

    At omega|ml we use the following open source technologies to operate k8s
    clusters across several cloud providers. This is also the recommended set up
    - effectively this is the cloud manager.

    * Rancher - to manage the deployment and operation of k8s clusters,
      including operational monitoring, alerting, resource limits etc.
    * Terraform - to manage cloud resources made available to k8s (i.e. nodes)
    * Helm - to provide the scripting of omegaml component deployment

    The omega|ml cloud provider edition includes example scripts for both the
    deployment of Rancher as well as the operation of the cluster using Terraform
    as a middleware between cloudmgr and Rancher.

Kubernetes
----------

omega|ml managed service deployment is based on Kubernetes. In a nutshell,
a functional full deployment needs the following minimum setup:

Nodes
+++++

* omegaml.io/role=dbmaster - 1 node, 2 cores, 4GB (hosts MySQL and MongoDB)
* omegaml.io/role=system - 1 node, 2 cores, 4GB (hosts omegaweb, cloudmgr, jupyterhub)
* omegaml.io/role=worker - 1 node, 2 cores, 2GB (hosts jupyer instances and runtime workers)

Disks
+++++

The dbmaster will need two persistent volumes attached:

* mongodb - the volume to host MongoDB
* mysql   - the volume to host mysql

Other persistent volumes may be required to host client-specific storage.

Notes:

* this set up will run the omega|ml system confortably, but it will
  not be very useful for real data science work. In particular a data science
  work place needs to have at least 4 cores/8GB in order to provide a useful
  environment. This is not a property of omega|ml but a due to the nature of
  data science in general (if you are a cloud provider, this should be good
  news: your users will want many & larger worker instances than this minimum
  set up)

* from a technical point of view, there is no need to have three nodes, in
  fact one node with say 4cores/8GB would be sufficient to run the managed
  service. However this is not recommended as it makes maintenance and
  performance tuning more difficult


Opsmgr
------

The opsmgr needs to provide at least the following services to operate a
cluster on behalf of users:

* omegaml - this the only service that is technically needed. it configures
  user accounts on user sign up and deploys access to shared resources (namely
  runtime worker and analytics storage)

Additional services can be configured to enable users or administrators to
automatically set up

* jupyter workers - k8s resources that run user-launched jupyter notebooks
* runtime workers - k8s resources that run user-launched runtime jobs
* dedicated storage - k8s resources that host user-specific storage

Helm
----

The cloud provider edition includes several helm charts for easy configuration
and deployment of the various k8s resources:

* omegaml-ingress - this will set up the ingress to all components in omega|ml
* omegaml-system -  this composes the infrastructure components, mysql, mongodb,
  jupyter as a service, omega web app
* omegaml-storage - provides the persistent volumes for mongodb and mysql
* omegaml-worker  - deploys user-launched worker instances

Each of the chart is configurable.

