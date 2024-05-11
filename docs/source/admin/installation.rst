Platform installation
=====================

Pre-Requisites
--------------

* Helm v2.x or higher
* kubectl
* deployment rights to a kubernetes cluster
* access to a repository providing dependent image, or configured services

Helm Charts
-----------

omega-ml provides the following helm charts to deploy the platform to a
kubernetes cluster:

* *omegaml-tenant* - deploys all *omegaml-services* components. With this
  chart installed, the platform is fully operational.

* *omegaml-runtime* - deploys the omegaml-runtime configuration, configured for
  a particular user

* *omegaml-worker* - deploys one instance of the omega-ml worker (a rabbitmq client),
  using the configuration provided by the *omegaml-runtime* chart.

* *omegaml-appingress* - deploys an Ingress configured to access a particular
  user application as deployed by the apphub component (optional)

Cluster preparation
-------------------

The helm charts are pre-configured to make use of two distinct types of
nodes, using respective `nodeSelectors`. Roles with this designation should
be prepared by your cluster administrators.

* `omegaml.io/role=system` - all *omegaml-services* components
* `omegaml.io/role=worker` - all *omegaml-runtime* components


Step-by-Step installation
-------------------------

The following steps deploy a fully functional omegaml-instance on your
cluster:

1. Install the *omegaml-tenant* chart::

    $ helm upgrade --install omegaml helmcharts/omegaml-tenant --values values.yaml --namespace omegaml-services --create-namespace

2. Install the *omegaml-runtime* chart::

    $ helm upgrade --install omegaml-runtime helmcharts/omegaml-runtime --values values.yaml --namespace omegaml-runtime --create-namespace

3. Install the *omegaml-worker* chart::

    $ helm upgrade --install omegaml-worker helmcharts/omegaml-worker --values values.yaml --namespace omegaml-runtime

Chart configuration
-------------------

The full specification of values that can be configured by each chart are
included in each chart's README. This is a synopsis of the major configuration
options.

Tags
++++

The *omegaml-tenant* chart provides a series of *tags* that can be configured
to select specific components for installation. For example, if your environment
provides ready-made storage services (i.e. MongoDB), you should
set the respective tags to `false`::

    # values.yaml
    tags.mongodb: false


Example deployment
------------------

Using k3d and docker we can deploy a fully functional kubernetes cluster and
instance of omega-ml as follows:

.. code:: bash

    # Makefile
    export KUBECONFIG=${HOME}/.kube/k3d-test-config.yml

    setup:
        which docker || echo "you must install docker first"
        curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
        curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

    cluster:
        # create local k8s cluster
        # disable traefik https://k3d.io/v5.4.1/design/concepts/?h=traefik#example
        # use host dns https://bytemeta.vip/repo/rancher/k3d/issues/1017
        export K3D_FIX_DNS=1 && k3d cluster create test --k3s-arg "--disable=traefik@server:0"
        k3d kubeconfig get test  > ${KUBECONFIG} && chmod 600 ${KUBECONFIG}
        k3d node create test-omegaml-system -c test --k3s-node-label "omegaml.io/role=system"
        k3d node create test-omegaml-worker -c test --k3s-node-label "omegaml.io/role=worker"
        # deploy nginx ingress instead of traefik
        helm upgrade --install ingress-nginx ingress-nginx --repo https://kubernetes.github.io/ingress-nginx --namespace ingress-nginx --create-namespace --values nginx-values.yaml

    tenant:
        # deploy omegaml to existing cluster
        kubectl delete configmap ingress-nginx-tcp -n ingress-nginx || echo "deleted configmap ingress-nginx-tcp for replacement"
        helm upgrade --install omegaml helmcharts/omegaml-tenant --values values.yaml --namespace omegaml-services --create-namespace
        helm upgrade --install omegaml-runtime helmcharts/omegaml-runtime --values values.yaml --namespace omegaml-runtime --create-namespace
        helm upgrade --install omegaml-worker helmcharts/omegaml-worker --values values.yaml --namespace omegaml-runtime

    uninstall:
        # remove everything
        helm uninstall omegaml -n omegaml-services
        helm uninstall omegaml-runtime -n omegaml-runtime
        helm uninstall omegaml-worker -n omegaml-runtime

    stop:
        # stop the cluster
        k3d cluster stop test

    remove: uninstall stop
        k3d cluster delete test
        k3d node delete --all

    dashboard:
        kubectl -n omegaml-services get secret $(shell kubectl -n omegaml-services get sa/cluster-admin -o jsonpath="{.secrets[0].name}") -o go-template="{{.data.token | base64decode }}" | xargs echo
        browse "https://omega-172.29.0.2.nip.io/k8s/"



