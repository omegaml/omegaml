#!/usr/bin/env bash
## package
##
## Deploy to kubernetes cluster
##    @script.name [option]
##
##    --full-client      open all ports including mongodb, rabbitmq
##    --clean            delete all services, pods, configmaps, secretsbefore, DBs before redeploy
##
# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit
source $script_dir/omutils || exit

# specifics for this client
METALB_CONFIG="./ncloud/metalb-configmap.yml"
SSH_KEY=$HOME/.ssh/ncloud_rsa.pem

# build args for deploy-rancher-k8s
DEPLOY_ARGS=""
if [[ ! -z $clean ]]; then
    DEPLOY_ARGS="$DEPLOY_ARGS --clean"
fi

# kick off the deployment
$script_dir/deploy-rancher-k8s.sh --sshkey $SSH_KEY --config $HOME/.omegaml/ncloud-config.yml $DEPLOY_ARGS
