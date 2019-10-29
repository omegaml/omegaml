#!/usr/bin/env bash
## package
##
## Deploy to kubernetes cluster set up by rancher
##
## Make sure KUBECONFIG is set to the correct cluster before you deploy
## (check using kubectl cluster-info)
##
##    @script.name [option]
##
##    --sshkey=VALUE         ssh key file
##    --config=VALUE         configuration file, defaults to ./k8sconfig/config.yaml
##    --admin-email=VALUE    admin email address for omega web
##    --admin-password=VALUE admin password for omega web
##    --admin-apikey=VALUE   jupyter hub apikey
##    --metallb=VALUE        metallb config file
##    --acme=VALUE           the letsencrypt acme challenge file
##    --full-client          open all ports including mongodb, rabbitmq
##    --clean                delete all services, pods, configmaps, secretsbefore, DBs before redeploy
##
## Required: sshkey
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

# kube specifics
K8S_CONFIG=${config:=./k8sconfig/config.yaml}
SSH_KEY=${sshkey:=/.ssh/id_rancher}
METALLB_CONFIG=${metallb:=}
ACME_CHALLENGE=$(acme:=./.omegaml/letsencrypt/challenge)

# omegaml settings
OMEGA_ADMIN_EMAIL=${admin_email:="admin@omegaml.io"}
OMEGA_ADMIN_PW=${admin_password:="test"}
OMEGA_JYADMIN_APIKEY=${admin_apikey:="b7b034f57d442e605ab91f88a8936149e968e12e"}
OMEGA_OMOPS_APIKEY=${admin_apikey:="b7b034f57d442e605ab91f88a8936149e968e12e"}

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
  echo "This is used for the cluster to pull the private omegaml-ee image from duckerhub"
  echo "Note the dockerhub user must be authorized to access the omegaml/omegaml image."
  exit 1
fi

DOCKER_SERVER=https://index.docker.io/v1/
DOCKER_USER=`cat $HOME/.omegaml/docker.creds | grep USER | cut -f 2`
DOCKER_PASSWORD=`cat $HOME/.omegaml/docker.creds | grep PASSWORD | cut -f 2`
DOCKER_EMAIL=`cat $HOME/.omegaml/docker.creds | grep EMAIL | cut -f 2`
DBMASTER_NODE=`kubectl get nodes -l omegaml.io/role=dbmaster -o name | cut -d '/' -f 2`
DBMASTER_USER=ubuntu

if [[ $clean ]]; then
  echo "Deleting all previously installed components"
  kubectl delete -f $script_dir/kubernetes
  kubectl delete -f $script_dir/kubernetes/config
  kubectl delete secret docker-registry regcred
  kubectl delete configmap nginx-conf
  echo "Components deleting. Giving the cluster some time to clean up..."
  countdown 30
  echo "Erasing previous data for mongodb and mysql on master node $DBMASTER_NODE"
  ssh -i $SSH_KEY $DBMASTER_USER@$DBMASTER_NODE sudo rm -rf /data/mysql /data/mongodb
  ssh -i $SSH_KEY $DBMASTER_USER@$DBMASTER_NODE sudo mkdir -p /data/mysql
  ssh -i $SSH_KEY $DBMASTER_USER@$DBMASTER_NODE sudo mkdir -p /data/mongodb
fi

# set secret for private docker repository access
#   this is used in the imagePullSecret tag
echo "Creating dockerhub login secret from $HOME/.omegaml/docker.creds"
kubectl create secret docker-registry regcred --docker-server=$DOCKER_SERVER --docker-username=$DOCKER_USER --docker-password=$DOCKER_PASSWORD --docker-email=$DOCKER_EMAIL

# generate config maps
echo "Generating k8s configmaps using $K8S_CONFIG into ./kubernetes/config"
configfiles=$(find ./k8sconfig -name "*configmap*" | xargs)
for cf in $configfiles; do
  tpl --yaml $K8S_CONFIG $cf > ./kubernetes/$cf
done

# deploy
echo "Deploying images and configuring services"
kubectl create configmap nginx-conf --from-file etc/nginx/nginx.conf --from-file etc/nginx/http.conf --from-file etc/nginx/stream.conf
kubectl create configmap letsencrypt-conf --from-file $ACME_CHALLENGE
kubectl apply -f $script_dir/kubernetes/config
kubectl apply -f $script_dir/kubernetes

# serve
echo "Waiting for services to become available"
find ./kubernetes -name "*deployment.yaml" | xargs -L1 kubectl rollout status -f
echo "Services deployed. Giving some time to spin up..."
countdown 30

# install lb
if [ ! -z $metallb ]; then
  kubectl apply -f https://raw.githubusercontent.com/google/metallb/v0.7.3/manifests/metallb.yaml
  kubectl apply -f $METALLB_CONFIG
fi


# configure services
echo "Execute one-off admin tasks to the omegaml web app and enable security"
cat scripts/mongoinit.js | podssh mongodb mongo
podssh omegaml python manage.py migrate
podssh omegaml python manage.py loaddata landingpage.json
podssh omegaml python manage.py omsetupuser --username admin --email $OMEGA_ADMIN_EMAIL --password $OMEGA_ADMIN_PW --admin --nodeploy
podssh omegaml python manage.py omsetupuser --username jyadmin --staff --apikey $OMEGA_JYADMIN_APIKEY
podssh omegaml python manage.py omsetupuser --username omops --staff --apikey $OMEGA_OMOPS_APIKEY

# finish with a nice message
echo "Installation complete. Access at http://HOST:5000"
