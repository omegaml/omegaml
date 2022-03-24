Account Manager
===============

The Account Manager component Responsibilities include:

* user sign up handling, e.g. generation of API keys, configuration of user
  profile (`omegaweb`)
* execution of periodic tasks, e.g. maintenance (`omegaops`)

Cloud Manager
=============

The Cloud Manager component is central to the provisioning of a managed
MLOps service in that it provides the backend to operating the service
in a private or public cloud environment.

Responsibilities include:

* provision of services, including cloud resources, installation of user-
  specific components and similar (`cloudmgr`)
* service usage tracking to enable service-based charging & billing
* billing backend, including itemized invoices and payment

Cloud Manager exposes a straight forward data model & REST API
that enables authorized users to define and manage the services available
and their deployment for each user, including installation,
scaling, health checking and eventual removal.

Data Model
==========

The core entities cover the specification of service offerings and their
associated deployment steps as well as tracking the status of each deployment.

* `ServicePlan` - each plan represents some service that the provider wishes
  to offer to users, or provide as a backend service for its own operations.
  At a minimum an omega|ml managed service instance provides the `omegaml`
  service. This can be extended to include e.g. `worker`, `storage` and
  `jupyter notebook` services which can be deployed on a per-user basis.

* `ServiceConfiguration` - a configuration is the description of the tasks
  required to deploy a service. For each configuration multiple tasks can
  be specified, which all have to complete without error before a service
  is considered to have deployed successfully. A task is typically implemented
  as a shell or python script. Scripts can be pre-installed, or can be
  dynamically fetched from a repository every time the task executes.

* `ServiceDeployment` - a deployment tracks one specific deployment of a service
  (for a user). For example, if a new user signs up to omega|ml, a deployment
  will be created for this user, enabling the user to start a Jupyter Notebook,
  to use the analytics storage and to submit jobs to the omega|ml runtime

The workflow entities track the execution of user requesets. A user request
is a request to perform either installation, configuration or removal of a
service.

* `ServiceCommand` - a user issues a command relative to some offering (to
  create a new deployment), or relative to some existing deployment (to
  perform configuration or removal).

* `ServiceTask` - a task tracks the execution of one step described in a
  service's configuration.

Commands, deployments and tasks all share the same state model:

* INITIATED (0) - the initial state, set whenver the object is created
* PENDING (1) - the object has been scheduled for execution
* COMPLETD (5) - execution has completed successfully
* REMOVED (8) - the component was removed (kept for history). Note a component
  in the process of being removed will have a status of PENDING
* FAILED (9) - some part of the execution has failed

(n) is the value of the status flag returned by the API.


API
===

The API consists of two parts:

1. administration - this relates to the core entities
2. commands -his relates to the issuing of comamnds and tracking of their
   executions

Note that administration is generally restricted to users with admin
priviledges, while command execution is open to registered users with an
active profile.

The API is available from the command line as well as the REST API (partially).

Management CLI
++++++++++++++

.. autosummary::

    paasdeploy.management.commands.createservice.Command
    paasdeploy.management.commands.deleteservice.Command
    paasdeploy.management.commands.deployservice.Command
    paasdeploy.management.commands.listservices.Command

.. autoclass::  paasdeploy.management.commands.createservice.Command
.. autoclass::  paasdeploy.management.commands.deleteservice.Command
.. autoclass::  paasdeploy.management.commands.deployservice.Command
.. autoclass::  paasdeploy.management.commands.listservices.Command


REST API (overview)
+++++++++++++++++++

.. autosummary::

    landingpage.api.signup.SignupResource
    landingpage.api.reset.ResetResource
    landingpage.api.user.UserResource
    paasdeploy.api.service.ServicePlanResource
    paasdeploy.api.service.ServiceConfigurationResource
    paasdeploy.api.command.ServiceCommandResource

landingpage.api
+++++++++++++++

.. autoclass:: landingpage.api.signup.SignupResource
.. autoclass:: landingpage.api.reset.ResetResource
.. autoclass:: landingpage.api.user.UserResource

paasdeploy.api
++++++++++++++

.. autoclass:: paasdeploy.api.service.ServicePlanResource
.. autoclass:: paasdeploy.api.command.ServiceCommandResource


