#!/bin/bash
## package
##
## Deploy to kubernetes cluster
##    @script.name [option]
##

# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit

DOCKER_SERVER=https://index.docker.io/v1/
DOCKER_USER=`cat $HOME/.omegaml/docker.creds | grep PASSWORD | cut -f 2`
DOCKER_PASSWORD=`cat $HOME/.omegaml/docker.creds | grep PASSWORD | cut -f 2`
DOCKER_EMAIL=`cat $HOME/.omegaml/docker.creds | grep EMAIL | cut -f 2`

function podssh() {
  pod=`kubectl get pods -o name | grep $1 | cut -d / -f 2 | head -n1`
  shift 1
  cmd=${@:-bash}
  kubectl exec -it $pod -- $cmd
}

# set secret for private docker repository access
#   this is used in the imagePullSecret tog
microk8s.kubectl create secret docker-registry regcred --docker-server=$DOCKER_SERVER --docker-username=$DOCKER_USER --docker-password=$DOCKER_PASSWORD --docker-email=$DOCKER_EMAIL

# enable ip forwarding and routing on the host, and inter-pod cluster dns
#   this is required to allow pods to access the internet
sudo ufw default allow routed
sudo ufw allow in on cbr0 && sudo ufw allow out on cbr0
microk8s.enable dns

# deploy
microk8s.kubectl create configmap nginx-conf --from-file etc/nginx/nginx.conf --from-file etc/nginx/http.conf --from-file etc/nginx/stream.conf
microk8s.kubectl apply -f $script_dir/kubernetes

# serve
echo "Waiting for services to become available"
sleep 10
nohup microk8s.kubectl port-forward service/nginx 5000:5000 8888:8888 > server.log &

# configure services
podssh omegaml python manage.py loaddata landingpage.json
podssh omegaml python manage.py createsuperuser
cat scripts/mongoinit.js | podssh mongodb mongo