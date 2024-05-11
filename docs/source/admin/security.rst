Security
========

Principles
----------

omegaml commercial edition follows the 12-factor principles for all
service configuration. This means that all services are decoupled from
the specific services they consume, and are only coupled at runtime by
means of retrieving credentials from their environment. This applies to
omegaml clients and runtime workers alike, meaning that clients and
runtime workers can be attached to omegaml clusters by configuration.

Client and Worker sessions
--------------------------

Following the above principle, omegaml clients and runtime worker are required
to retrieve the runtime configuration from their environment. There are
two sources to retrieve this configuration:

1. the operating system environment (injected from k8s ConfigMap and Secrets)
2. the omegaml cloud manager `/config` REST API service

.. image:: /images/security-model-principles.png

Client sessions
+++++++++++++++

Clients are required to login to the cluster by issuing the following
command.

.. code:: bash

    $ om login USERID PASSWORD --apiurl http://omegaml.yourdomain.com

This triggers a call to the `/config` REST service of the webui, aka
the cloud and account manager. This will retrieve the session configuration
from the user's assigned `omegaml` Service Deployment, and return it to
the client. The client stores the credentials in a `config.yml` file.

Upon calling any other omegaml command, or when using the omegaml library
from a Python or R script, the client will create an authorized `Omega()`
instance by again calling the `/config` service, using the credentials
previously stored in `config.yml`.

Runtime worker sessions
+++++++++++++++++++++++

Runtime workers operate equivalently to any other omega-ml clients in principle,
however runtime workers are generally run non-interactively and thus do not
require an explicit login. Instead they use the operating system environment
(`OMEGA_USERID`, `OMEGA_PASSWORD` variables) to retrieve their initial session.
The initial session of a runtime worker is required to establish the
connection to the cluster (namely RabbitMQ and MongoDB).

For user-initiated tasks, the runtime worker will perform the same steps
as any other client. Namely it will call the `/config` service


User Authentication
-------------------

The platform accepts the following types of user authentication:

* email / password (for web and admin)
* userid / apikey (API, jupyterhub, apphub)
* JWT token (API, jupyterhub, apphub)

Email / Password
++++++++++++++++

Every user is associated with at least one default email address, whereby
this email address is a unique identifier for this user. The password can
be chosen by the user, unless user registration is blocked.

API Keys
++++++++

Userid and API keys are automatically issued by the platform upon user
registration.

JWT Token
+++++++++

The platform can issue JWT tokens or accept signed JWT tokens from other
authenticators. See jwtauth.rst for details.

User Model
----------

Users are organized into roles and groups. Roles include admin, staff
and users. Admin users automatically have all permissions to change and
access all settings, including to perform actions on behalf of other users.
Staff users can be assigned specific create/update/delete permissions for
parts of the settings. Normal users can only access their own objects
through the REST API and cannot directly access or change any of the
settings.

Arbitary groups can be created by admin and staff roles. If a user is a
member of a group, the groups settings are applied in a cascading manner
over the user's own settings. That is, if a particular settings is not
defined for a user, its corresponding group settings will be returned.

Groups
------

Groups must be defined as follows:

1. Create a group `<group>`
2. Create a corresponding group user `G<group>`

It is necessary to define the group user because the group's settings are
associated with the user, not the group itself. A user can be associated with
none, one or many groups. Note that group users cannot be part of other groups.

Service Deployments
-------------------

Service Deployments store credentials to MongoDB and RabbitMQ. These
credentials are stored in the SQL DB configured to the webui. In order
to increase security
