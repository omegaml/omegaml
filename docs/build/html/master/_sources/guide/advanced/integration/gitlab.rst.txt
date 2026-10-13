Integrate with Gitlab CI/CD
===========================

.. _gitlab_cicd: https://about.gitlab.com/blog/2017/09/21/how-to-create-ci-cd-pipeline-with-autodeploy-to-kubernetes-using-gitlab-and-helm/
.. _gitlab_k8s: https://kubernetes.io/docs/concepts/containers/images/#updating-images

Update deployment
-----------------

Once the image is ready it can be deployed to kubernetes using kubectl
(this is as with any kubernetes cluster, i.e. not specific to omega-ml):

.. code:: bash

    $ kubectl set image deployment/<deployment name> <container name>=<repo/image:version> --record

As an alternative you could also update your deployment.yml, setting the
image version there. Then you can run

.. code:: bash

    $ kubectl apply -f deployment.yaml


Using the same image tag for testing
------------------------------------

Note the above only works if every newly built image is tagged with a new version.
Otherwise kubernetes will not update the image as it thinks it already has the latest
version. For testing it is more convenient to use the :code:`:latest` image tag, and set
the :code:`pullPolicy: Always` as described in gitlab_k8s_. Then you can simply delete
the pod(s). Since the deployment requires at least one pod, kubernetes will create
a new pod and pull the image again (that’s what Always means):

.. code:: bash

    $ kubectl delete pods -l name=<label>

Configure kubectl
-----------------

Note to make this work inside the gitlab pipeline, kubectl needs to be configured
to access the omegaml kubernetes instance, using the cloudmgr-provided kube config
file. The kubectl configuration (kube config) is available from the cloudmgr:

1. login to cloudmgr
2. select the Cluster
3. Click :code:`Kubeconfig File` and download or copy/paste the kube config file

The easiest is to put the contents of the kube config into a gitlab variable e.g.
copy/paste the output of the following command to the :code:`kube_config` variable
(I’m following this gitlab_cicd_ example).

.. code:: bash

    # run locally, copy paste output to kube_config variable
    $ cat ~/.kube/config | base64
    In your gitlab pipeline, before running kubectl do the following

.. code:: bash

    echo ${kube_config} | base64 -d > $HOME/.kube

To check whether kubectl is configured correctly run the following command as part of the pipeline. If the configuration works as expected, it will print something like this (or an error message otherwise).

.. code:: bash

    kubectl cluster-info
    Kubernetes control plane is running at https://cloudmgr.omegaml.io/k8s/clusters/c-jgnm5

