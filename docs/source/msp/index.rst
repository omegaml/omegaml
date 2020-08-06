Managed Service Edition
=======================

This documents the omega|ml managed service edition installation, configuration and
operations. The omega|ml managed service edition is a fully cloud-enabled variant
of omega|ml enterprise that enables cloud providers to offer their clients
analytics services as a fully managed service.

The edition consists of the following components

* :code:`omegaee` - the omega|ml enterprise edition, providing security features
  for the runtime and storage in an omega|ml cluster, as well as Apache Spark
  integration (in development)
* :code:`omegaweb` - the platform's REST API, web interface and dashboard, including
  user signup, outbound email and user profile handling
* :code:`jupyterhub` - the notebook service for interactive data science, providing
  Jupyter Notebooks as a service
* :code:`omegaops` - the operations component, providing user management, scheduled
  operations, as well as the user-facing APIs for deployment and scaling of
  backend and cluster resources
* :code:`cloudmgr` - the cloud manager component, providing for the deployment,
  operations and monitoring of Kubernetes clusters running omega|ml (optional)
* :code:`apphub` - (in development) an application service, providing for fast
  deployment of data science applications and custom dashboards

This chapter described the `omegaops` and `cloudmgr` components in more detail.

.. toctree::
   :maxdepth: 2

   omegaops
   cloudmgr
   admin
