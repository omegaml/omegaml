Components
==========

Concepts & Platform Layers
--------------------------

The omega-ml platform is built from the following conceptual layers:

* *Processing and delivery* - functional components used by data scientists and
  end-users (such as ML pipelines, feature stores, ML applications and APIs).

* *Metadata, Storage and Runtime* - easy to use storage and computation resources
  which provide the power and flexibility of distributed computing, while shelding
  data scientists and data engineers from the complexity of the underlying technology.

* *Deployment Platform* - the basic technology that runs the platform, packaged
  in readily deployable microservices such that DevOps engineers can configure
  and deploy all components efficiently and effectively, without the complexity
  of a traditional ML engineering.

Processing and delivery
+++++++++++++++++++++++

This layer provides the various APIs for the users to store models, scripts,
jobs, apps and data. The APIs include Python, R, command-line and a REST API.
Technically this layer consists of the client component (the omegaml package),
a web UI & backend that provides account management, configuration
services and the REST API.

Metadata, Storage and Runtime
+++++++++++++++++++++++++++++

This layer provides a generic storage service that can store any object,
or at least a reference to a third-party source. Once an object is stored,
a Metadata entry is created, which holds the name of the object, its storage
location and further user-defined attributes. The combined Metadata of all
objects form the platform's storage index through which all objects can be
accessed, retrieved and manipulated.

The runtime consists of one or more "workers". A worker is a process that
waits for task messages and upon receiving will start processing a task
and return its result. The technology (Python Celery/RabbitMQ) allows for
both horizontal (more workers) and vertical scaling (workers with parallel
processes), which makes it an ideal choice for dynamic computing needs.

This layer also provides a plugin system that allows to associate different
types of stored objects with specific plugins. For example, if you store a
reference to a table in an SQL database, this object is associated with
the SQLPlugin that knows how to access the SQL database. This association is
by the means of a "kind" attribute in each Metadata entry, and each "kind" value
is linked to a particular plugin. The plugin system makes the platform
easy to extend and it can be adapted to different requirements.

Deployment Platform
+++++++++++++++++++

This layer provides the actual implementation of the above concepts. The
platform comes packaged as a set of micro-services deployed and configured
using 12-factor principles. This is ideal for a Docker or Kubernetes-based
deployment, however there is no hard coupling to either of these.

omega-ml at its core requires just two key components to run:

* RabbitMQ - as the communications layer
* MongoDB - as the principal storage

The platform adds components to enable multi-tenant and multi-user setups and
to provide additional services for data science development and easy application
deployment.

* Web UI & Backend (required) - provides account management and configuration services
* Cloud Manager (required) - provides user-callable, scriptable, dynamic workflows to configure and
  scale the platform by issuing simple commands
* Jupyterhub (optional) - provides a pre-configured Jupyter Notebook environment so data scientists can
  be productive without installing custom software on their workstations
* Apphub (optional) - provides a simple way to start small analytics apps and dashboards without having to know
  the complexity and specifics of the deployment environment

Note that all of these components require a dedicated SQL database for management and runtime purpose
(MySQL, PostgreSQL, MSSQL).

.. note::

    Why do these components not use MongoDB for storage? MongoDB is a DDL-free document
    database, which makes it particularly well suited to store any kind of objects. It
    is typical of data science projects that there is a wide range of data to be considered
    and omega-ml leverages MongoDB's flexibility for this purpose. Further, MongoDB is
    easy to scale horizontally, which makes it well suited to high-volume, high-availability
    scenarios, another aspect typical of data scienc projects.

Technology
----------

The following maps omega-ml components to the respective technology
component as relevant to platform operations.

+------------------------+----------------------+--------------------------------+-------------------------------+
| **omega-ml component** | **technology**       | **purpose**                    | **layer**                     |
+------------------------+----------------------+--------------------------------+-------------------------------+
| REST APIs, Web UI      | Python (Django)      | Client APIs, Admin UI          | Processing and delivery       |
+------------------------+----------------------+--------------------------------+-------------------------------+
| Apphub                 | Python (Flask)       | Application hosting            | Processing and delivery       |
+------------------------+----------------------+--------------------------------+-------------------------------+
| JupyterHub             | Python (Tornado)     | Development sandbox            | Processing and delivery       |
+------------------------+----------------------+--------------------------------+-------------------------------+
| Metadata               | MongoDB              | Object metadata                | Metadata, Storage and Runtime |
+------------------------+----------------------+--------------------------------+-------------------------------+
| Storage                | MongoDB + SQL-DBs*   | Data managed by omega-ml,      | Metadata, Storage and Runtime |
|                        |                      | includes data & model tracking |                               |
+------------------------+----------------------+--------------------------------+-------------------------------+
| Runtime                | Python, RabbitMQ     | Messaging (MQ)                 | Metadata, Storage and Runtime |
+------------------------+----------------------+--------------------------------+-------------------------------+
| Cloud manager          | Helm, Terraform, K8s | Deployment & operations        | Deployment Platform           |
+------------------------+----------------------+--------------------------------+-------------------------------+
| (custom provided)      | Graphana, Prometheus | Operations Monitoring          | Deployment Platform           |
+------------------------+----------------------+--------------------------------+-------------------------------+





