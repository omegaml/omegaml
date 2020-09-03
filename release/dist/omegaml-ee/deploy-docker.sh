#!/bin/bash
## package
##
## Deploy to docker using docker-compose
##    @script.name [option]
##
## Options:
##    --clean       run docker-compose down before starting
##

# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/scripts/easyoptions || exit
source $script_dir/scripts/omutils || exit
pushd $script_dir

# launch and wait for services to start
if [[ ! -z $clean ]]; then
    echo "Removing services..."
    docker-compose down --remove-orphans
    echo "Services removed."
fi
echo "Starting services"
docker-compose up -d
waiton "Waiting for services to have initialised" http://localhost:5000
docker-compose up -d nginx

# apply configurations
echo "Securing mongodb"
cat scripts/mongoinit.js | compose_exec mongodb mongo
docker-compose exec omegaml scripts/initlocal.sh

# finalize
popd
