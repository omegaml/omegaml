Settings
========

The platform is configured in three levels:

* *static settings* are defined in configuration files and environment variables.
  Static settings cannot be changed at run-time

* *Runtime constants* provide platform-wide defaults. These can be be changed
  at runtime by an admin user and take immediate effect. If a service
  configuration is undefined, the runtime constance are used instead.

* *Service configuration* provide service-specific settings, also known as
  client configurations. These are queried by platform clients at runtime
  to retrieve the per-session configuration. While the platform, through its
  cloud manager component, can offer and deploy any admin-defined service,
  the main service is the 'omegaml' service, which is deployed automatically
  upon user sign up.

Static Settings
---------------

Runtime Constants
-----------------

Service Configurations
----------------------
