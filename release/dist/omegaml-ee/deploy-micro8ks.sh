#!/bin/bash
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

# ports as published by k8 cluster
DASHBOARD_PORT=5000
JYHUB_PORT=8888
MONGODB_PORT=27017
RABBITMQ_PORT=5672
# ports as mapped to localhost
LOCAL_DASHBOARD_PORT=5000
LOCAL_JYHUB_PORT=8888
MONGODB_PORT=27017
RABBITMQ_PORT=5672
# image
image="omegaml/omegaml-ee"

# ports to forward after deployment
if [[ ! $full_client ]]; then
    PORTS="5000:5000 8888:8888"
else
    PORTS="5000:5000 8888:8888 27017:27017 5672:5672"
fi

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
  microk8s.kubectl delete -f $script_dir/kubernetes
  microk8s.disable dns
  microk8s.kubectl delete secret docker-registry regcred
  microk8s.kubectl delete configmap nginx-conf
fi

# set secret for private docker repository access
#   this is used in the imagePullSecret tog
echo "Creating dockerhub login secret from $HOME/.omegaml/docker.creds"
microk8s.kubectl create secret docker-registry regcred --docker-server=$DOCKER_SERVER --docker-username=$DOCKER_USER --docker-password=$DOCKER_PASSWORD --docker-email=$DOCKER_EMAIL

# pull image so it is here for the pods to use
echo "Pulling docker image $image to speed up pod startup later"
microk8s.docker image pull $image

# enable ip forwarding and routing on the host, and inter-pod cluster dns
#   this is required to allow pods to access the internet
echo "Enabling firewall to route to microk8s pods"
sudo ufw default allow routed
sudo ufw allow in on cbr0
sudo ufw allow out on cbr0
microk8s.enable dns

# deploy
echo "Deploying images and configuring services"
microk8s.kubectl create configmap nginx-conf --from-file etc/nginx/nginx.conf --from-file etc/nginx/http.conf --from-file etc/nginx/stream.conf
microk8s.kubectl apply -f $script_dir/kubernetes

# serve
echo "Waiting for services to become available"
find ./kubernetes -name "*deployment.yaml" | xargs -L1 kubectl rollout status -f
echo "Services deployed. Giving some time to spin up..."
countdown 30

# configure services
echo "Execute one-off admin tasks to the omegaml web app and enable security"
cat scripts/mongoinit.js | podssh mongodb mongo
podssh omegaml python manage.py loaddata landingpage.json
podssh omegaml python manage.py createsuperuser
podssh omegaml python manage.py omsetupuser --username jyadmin --staff --apikey b7b034f57d442e605ab91f88a8936149e968e12e

# setting up port forwarding
echo "Setting up port forwarding as $PORTS"
nohup microk8s.kubectl port-forward service/nginx $PORTS > server.log &

# finish with a nice message
echo "Installation complete. Access at http://localhost:5000"
