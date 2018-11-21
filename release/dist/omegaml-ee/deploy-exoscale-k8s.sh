#!/usr/bin/env bash
## package
##
## Deploy to kubernetes cluster
##    @script.name [option]
##
##    --full-client      open all ports including mongodb, rabbitmq
##    --clean            delete all services, pods, configmaps and secretsbefore redeploy
##
# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit
source $script_dir/omutils || exit

# image
image="omegaml/omegaml-ee"
# ports as published by k8 cluster
DASHBOARD_PORT=5000
JYHUB_PORT=8888
MONGODB_PORT=27017
RABBITMQ_PORT=5672
KUBECONFIG=$PWD/exoscale/kube_config_cluster.yml

# print cluster info
kubectl cluster-info || echo "Error with kubectl"

# configuration for credentials
if [[ ! -f $HOME/.omegaml/docker.creds ]]; then
  echo "Create $HOME/.omegaml/docker.creds as"
  echo "--"
  echo "EMAIL=email@example.com"
  echo "USER=dockerhub user"
  echo "PASSWORD=dockerhub password"
  echo "--"
  echo "Note the dockerhub user must be authorized to access the omegaml/omegaml image."
  exit 1
fi

DOCKER_SERVER=https://index.docker.io/v1/
DOCKER_USER=`cat $HOME/.omegaml/docker.creds | grep USER | cut -f 2`
DOCKER_PASSWORD=`cat $HOME/.omegaml/docker.creds | grep PASSWORD | cut -f 2`
DOCKER_EMAIL=`cat $HOME/.omegaml/docker.creds | grep EMAIL | cut -f 2`

if [[ $clean ]]; then
  echo "Deleting all previously installed components"
  kubectl delete -f $script_dir/kubernetes
  kubectl delete secret docker-registry regcred
  kubectl delete configmap nginx-conf
  echo "Components deleting. Giving the cluster some time to clean up..."
  countdown 30
fi

# set secret for private docker repository access
#   this is used in the imagePullSecret tag
echo "Creating dockerhub login secret from $HOME/.omegaml/docker.creds"
kubectl create secret docker-registry regcred --docker-server=$DOCKER_SERVER --docker-username=$DOCKER_USER --docker-password=$DOCKER_PASSWORD --docker-email=$DOCKER_EMAIL

# deploy
echo "Deploying images and configuring services"
kubectl create configmap nginx-conf --from-file etc/nginx/nginx.conf --from-file etc/nginx/http.conf --from-file etc/nginx/stream.conf
kubectl apply -f $script_dir/kubernetes

# serve
echo "Waiting for services to become available"
find ./kubernetes -name "*deployment.yaml" | xargs -L1 kubectl rollout status -f
echo "Services deployed. Giving some time to spin up..."
countdown 30

# configure services
echo "Execute one-off admin tasks to the omegaml web app and enable security"
cat scripts/mongoinit.js | podssh mongodb mongo
podssh omegaml python manage.py loaddata landingpage.json
podssh omegaml python manage.py omsetupuser --username admin --email admin@omegaml.io --password test --admin --nodeploy
podssh omegaml python manage.py omsetupuser --username jyadmin --staff --apikey b7b034f57d442e605ab91f88a8936149e968e12e

# install lb
kubectl apply -f https://raw.githubusercontent.com/google/metallb/v0.7.3/manifests/metallb.yaml
kubectl apply -f exoscale/metalb-configmap.yml

# finish with a nice message
echo "Installation complete. Access at http://HOST:5000"
