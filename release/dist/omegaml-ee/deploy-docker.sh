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
# -- core service first, this starts rabbitmq, mongodb, mysql
docker-compose up -d omegaml
echo "Securing mongodb"
cat scripts/mongoinit.js | compose_exec mongodb mongo
docker-compose exec omegaml scripts/initlocal.sh
# -- worker services, connecting back to omegaml
docker-compose up -d worker omegaops
# -- UI applications
docker-compose up -d apphub omjobs
# - finally
docker-compose up -d nginx
waiton "Waiting for services to have initialised" http://localhost:5000

# finalize
popd
