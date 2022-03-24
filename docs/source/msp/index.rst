Commercial Edition
==================

This documents the omega|ml commercial edition installation, configuration and
operations. The omega|ml commercial edition is a fully cloud-enabled extension
of the omega-ml open-source edition, set up to be operated by enterprise internal
or public service providers.

omega-ml commercial delivers the following components

*   *Account Manager* - provides user management for the platform,
    the platform's REST API, web interface and dashboard, including
    user signup & management, outbound email and a UI for service configuration.

    It also provides the backend operations providing scheduled operations,
    backend operations services, as well as the user-facing APIs for deployment
    and scaling of omega-ml services and cluster resources

*   *Cloud Manager* - provides the cluster management for one or
    multiple cloud environments. It includes features to manage multiple
    tenants and their users.

*   *Application Services* - provides authenticated services to users of
    the platform. In particular,

    * :code:`jupyterhub for omegaml` - the notebook service for interactive data science,
      providing Jupyter Notebooks as a service, integrated with omega-ml
    * :code:`apphub` - an application service, providing for fast deployment of
      data science applications and custom dashboards

This chapter describes the `Account Manager` and `Cloud Manager` components in more detail.

.. toctree::
   :maxdepth: 2

   omegaops
   cloudmgr
   admin
