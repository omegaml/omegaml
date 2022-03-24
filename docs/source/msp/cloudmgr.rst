omega-ml Cloud Manager
======================

Concepts
--------

In a nutshell, cloudmgr is built on these core concepts:

* *Services* - a service that a user can command to install, update or remove.
  Services can be granular (e.g. "deploy PostgreSQL") or complex (e.g. "deploy
  a fully operational k8s cluster in one step").

* *Tasks* - a task that is executed to implement the user's command

* *Components* - the commands, templates, charts and scripts to execute in
  order to fulfill tasks.

* *Deployments* - a deployment is a user-specific instance of a service, and
  includes the specific configuration (specification parameters) requested
  by the user, as well as any configuration the service needs to record for
  further reference.

To manage the complexity of multi-tenant/multi-user deployments, cloudmgr is
built on two tiers, the *workflow* and the *execution* tiers.

* *Workflow* provides the user-exposed services via an API and keeps track of
  all tasks and their state. To keep Workflow easy to access and scale, this
  is implemented as a web application.

* *Execution* implements the components to fulfill service deployments, and
  manages the inventory of assets (e.g. configuration files, state information).
  To keep Execution easy to build and maintain, this is implemented as a set
  of bash scripts, Terraform templates and Helm charts.

Implementation model
--------------------

Let's look at the more detailed models that Workflow and Execution are built
on.

.. note:: Why not use existing devops tools like ansible, chef or puppet?

    While these are great tools, they have been built for the pre-cloud
    area. Their main focus is on the management of "servers", i.e.
    physical or virtualized machines. This is at odds with how the cloud
    works, and in particular how kubernetes (k8s) works.

    In a k8s cluster, the user specifies the components to be deployed, and
    the k8s scheduler decides on which machine the component gets run. That
    is, the whole concept of "running commands on a machine", which ansible
    etc. all are built for, is no longer adequate. While these tools can be
    made to work, there is really too much overhead in doing so. Also these
    tools were built for highly skilled DevOps engineers, not data teams.

    A simpler framework is needed.

    cloudmgr addresses this need. Cloud Manager is built for
    data scientists that just need to get some things done by writing a
    few scripts. It fully utilizes the k8s-area tools like Terraform and
    Helm, and extends these for the purpose of multi-tenant, multi-user
    management of cloud resources. If needed, tools like ansible,
    chef or puppet can of course be used to implement cloudmgr components.


Workflow models
+++++++++++++++

* *service plan* - the description of the user-exposed service, and what
  the user can do with it (e.g. how many items can be deployed).  e.g. the *cluster
  service* deploys a k8s cluster, the *tenant service* deploys an omega-ml site,
  etc.

* *service configuration* - the configuration of a service, in particular its
  configuration (e.g. env variables), the sequence of tasks required
  to execute a service command

* *service command* - a command issued by the user to order an action against
  a specific deployment (e.g. install, update, remove)

* *service task* - an asynchronous task to actually execute a command. A task
  can be sourced from a local script, a remote git repository or a python
  module.

* *service deployment* - a specific deployment of a service for a particular
  user

* *deployment worker* - this is a Celery worker that executes pending commands
  and tasks, and records their results


Execution models
++++++++++++++++

* *component* - the configuration of some executable service. A component
  links a service to either a script, a helm chart or a tensorflow template

* *templates* - the terraform templates and helm charts used to deploy
  a component

* *scripts* - the script(s) that executes all commands in response to a
  user's command against a specific deployment (e.g. install, update, remove)


User Guide
----------

cloudmgr provides several user interfaces

* REST API - to issue commands and query state of execution
* Admin UI - to add commands, view task status and output, optionally restart failed tasks
* workflow CLI - to issue commands from the command line
* execution CLI - to build, test, run and interact with deployments

We will look at each of these componenets while walking through a typical
user experience.


Deploying a service
+++++++++++++++++++

To deploy a service, call the REST API

.. code:: bash

    # issue command
    $ curl -X POST https://hub.omegaml.io/admin/api/v2/service/command
           -H 'Content-Type: application/json'
           -d '{
                "offering": "<plan name>",
                "user": "<userid>",
                "phase": "install",
                "params": "<specs>",
           }'
    < HTTP 201
    < Location: https://hub.omegaml.io/admin/api/v2/service/command/123

The parameters are as follows:

* :code:`<plan name>` - the name of the service plan (:code:`ServicePlan.name`)
* :code:`<userid>` - the user id (:code:`User.username`)
* :code:`<phase>` - the action to request, (:code:`install,update,remove`)
* :code:`<params>` - the parameters formatted as a string (:code:`key=value[,key=value...]`)

If we have a command line client, such as the one provided by omega-ml, we
can use this instead of the REST API:

.. code:: bash

    $ om cloud add <plan name> --specs "key=value"
    ...
    Done.
    $ om cloud update <plan name> --specs "key=value"
    ...
    Done.


Managing a service
++++++++++++++++++

Upon issuing a new command, the *deployment worker* will look up the service's
configuration and start all the tasks, in turn, to fulfill the request.
We can verify the status of the command and the corresponding tasks in
the admin UI:

.. image:: ../images/screenshots/cloudmgr-admin-command.png

For every task, at least a dispatching task and an execution task are created.

.. image:: ../images/screenshots/cloudmgr-admin-task.png

Or via the API:

.. code:: bash

    # get status
    $ curl https://hub.omegaml.io/admin/api/v2/service/command/123
    < HTTP 200
    < ...
    < status: PENDING


Building a service
++++++++++++++++++

1. Determine the service - e.g. "deploy a mongodb cluster"
2. Write the components - including all configuration files, scripts, templates
   and charts
3. Testing the service - running local tests, as if run by the deployment worker
4. Publish the service - register the service to the workflow


Service configuration
---------------------

Let's add the service configuration in :code:`services/mongodb-service.yml`

.. code::

    - plan: mongodb
      configuration:
        env:
          CLUSTER_PREFIX: om
      steps:
        - task: run
          params: >
            bash /data/cloudmgr/scripts/deploymongodb.sh


Service script
--------------

Next we need to define the service script in :code:`scripts/deploymongodb.sh`

.. code:: bash

    #!/bin/env bash
    script_dir=$(dirname "$0")
    . $script_dir/utils.sh
    . utils/env.sh

    function main() {
        cloudmgr helm.$DEPLOY_PHASE -c mongodb
    }

    localize_main

Note that this can be any bash-exectuable script you like, and you may use
any tools you like. The inclusion of utils.sh and env.sh provides a pre-defined
environment and directory template for multi-tenant/multi-user deployments.

The use of the cloudmgr helm command (instead of helm directly) ensures that the
component's configuration is passed correctly by generating a user-specific
values.yaml, according to the parameters given by the user.


Component configuration
-----------------------

In :code:`resources/components/scripts.yml`, we add the component's
configuration.

.. code::

    mongodb:
      envs: ''
      config: ~/.omegaml/cloudmgr.yml
      script: deploymongodb.sh
      vars_defaults:
        deploy_user_id: omadmin
      vars_map:
        cluster-name: node_prefix

In :code:`resources/components/helm.yml`, we add the component's helm chart:

.. code::

    runtime:
      args: *common_args
      envs: *common_envs
      chart: $HELM_LOCAL_CHARTS/mongodb
      namespace: default
      secrets_file: $COMPONENT_BASE/secrets.yaml
      values_file: $COMPONENT_BASE/values.yaml

Note the secrets_file and values_file items. These specify the location of the
files as generated by cloudmgr upon execution of the helm command. In particular,
the secrets file will contain *sops* secrets, replacing the corresponding entries
in values.yaml. The values file will contain the settings as used for the helm
deployment.

Testing the service
-------------------

.. code:: bash

    $ cloudmgr run -c mongodb --user someuser

This effectively simulates the execution of the mongodb command, including all
environment variables, values to the helm chart etc. set accordingly.

Deploying the service
---------------------

Finally, let's deploy the service

.. code:: bash

    $ python manage.py createservice --specs /data/cloudmgr/resources/services/mongodb-service.yaml

We can run a test by issuing a service command from the command line:

.. code:: bash

    $ python manage.py deployservice --phase uninstall  --service mongodb --user someuser --params "key=value"


Deploying omega-ml
==================

The omega|ml managed service runs best in a Kubernetes (k8s) environment hosted
at a cloud provider, where

* the k8s cluster manages the allocation of work loads
* the cloud provider manages the compute and storage resources
* cloudmgr works with the cluster and the cloud provider to deploy services,
  including the provision of additional nodes and the deployment or scaling
  of resources on the cluster

The omega|ml commercial edition includes the cloud manager component, a fully
scripted deployment for the deployment and operation of the omega-ml platform.
It can either be deployed to an existing k8s cluster, or deploy a new cluster,
using Rancher as a cluster manager (other cluster managers can be scripted).


Requirements
------------

* Kubernetes - omega|ml managed service deployment is based on Kubernetes.
  In a nutshell, a functional full deployment needs the following minimum
  setup:

    * omegaml.io/role=system - 1 node, 4 cores, 8GB

.. note::

    This set up will run the omega|ml system confortably, but it will
    not be very useful for real data science work. In particular a data science
    work place needs to have at least 4 cores/8GB as a seperate node in order
    to provide a useful environment. This is not a property of omega|ml but due
    to the nature of data science in general.

    At omega|ml we use the following open source technologies to operate k8s
    clusters across several cloud providers. This is also the recommended set up
    - effectively this is the purpose of the cloud manager.

    * Rancher - to manage the deployment and operation of k8s clusters,
      including operational monitoring, alerting, resource limits etc.
    * Terraform - to manage cloud resources made available to k8s (i.e. nodes)
    * Helm - to provide the scripting of omegaml component deployment

Components
----------

cloudmgr services
+++++++++++++++++

* tenant - deploys a fresh k8s cluster &  a fully operational omegaml cluster,
  optionally adding the account and cloudmgr itself
* nodepool - deploys and scales a nodepool to a Rancher cluster to be used
  for omega-ml runtime workers
* runtime - deploys and scales omega-ml workers, utilizing a specific nodepool
* registry - adds a docker registry credential to a third-party registry
* credential - adds Rancher credentials to a third-party cloud account
* appingress - adds a public endpoints to apphub apps, including ssl certs
* migrateuserdb - backup/restore the omega-ml mongodb from one account to another

Helm Charts
+++++++++++

The cloud provider edition includes several helm charts for easy configuration
and deployment of omega-ml. Each of the chart is configurable.

* omegaml-tenant - deploys a fully operational tenant cluster, optionally
  adding the account and cloudmgr itself
* omegaml-runtime - deploys a user's runtime environment
* omegaml-worker - deploys a user's worker instances
* omegaml-appingress - deploys public endpoints to apphub apps


Terraform Templates
+++++++++++++++++++

* credential - deploys Rancher credentials to a third-party cloud account
* registry - deploys k8s docker credentials to a third-party registry
* tenant - deploys a fresh k8s cluster using Rancher
* nodetemplates - deploys additional worker nodes in a Rancher-managed cluster

Bootstrapping
-------------

Deploy a k8s cluster
++++++++++++++++++++

**With Rancher**

If you operate a Rancher cluster, deploy a new k8s cluster by running:

.. code:: bash

    # provider is any of azu,aws,exo
    $ cloudmgr run -c cluster --specs "credentials=<name of credentials>,provider=<provider>"
    $ cloudmgr run -c tenant --specs "hub=true"

**Without Rancher**

Once your k8s cluster has been created and you are granted access, follow
these steps:

1. Prepare your configuration and k8s cluster setup

    * cloudmgr requires the right to deploy two namespaces::

        omegaml-services
        omegaml-runtime

    * cloudmgr requires the exposure of the following public ports (node ports).
      To achieve this, cloudmgr will attempt to update the ingress-nginx/tcp-services
      configmap to include this access. To disable, set tags.tcp-services=false.::

        # for non-ssl access (optional)
          27017: "omegaml-services/mongodb:27017"
          5672: "omegaml-services/rabbitmq:5672"
          5432: "omegaml-services/postgresql:5432"

       # for ssl access
          27018: "omegaml-services/tcp-services:27018"
          5671: "omegaml-services/tcp-services:5671"
          2345: "omegaml-services/tcp-services:2345"




   * SSL termination for these services is provided using a built-in nginx
     passthrough reverse-proxy, deployed as omegaml-services/tcp-services.
     The SSL certificates are managed by certmanager. To disable deployment
     of tcp-services, set tags.ssl=false. To disable certmanager deployment,
     set tags.certmgr=false. Without certmanager, be sure to deploy your
     own certificates to the omegaml-services/tcp-services pods.

   * Persistent Volumes are provided by either localpath-provisioner (dev) or
     the longhorn volume manager (production). If your cluster has its own
     PV provisionier, you should disable the localpath provisioner by setting
     tags.localpath=false. To deploy the longhorn volume manager, set
     the storage=cluster flag when deploying the k8s cluster via Rancher.

   * omega-ml uses NFS as an in-cluster shared fs for run-time updated
     configuration files. To disable the deployment of the integrated NFS
     server, set tags.nfs=false. In this case, make sure that the storage
     class "nfs" exists and is enabled for all workloads in the omegaml-services
     and omegaml-runtime namespaces.

2. Create the deployment structure and store your KUBECONFIG

    .. code:: bash

        # (bash)
        $ cloudmgr shell -c cluster --specs "provider=k8s"

        # (in cloudmgr shell)
        $ cat $KUBECONFIG > $CLUSTER_BASE/kubeconfig.yml
        $ exit

3. Deploy the tenant into your k8s cluster

    .. code:: bash

        # add any of the tags, as per above
        $ cloudmgr run -c tenant --specs "hub=true,provider=k8s"



