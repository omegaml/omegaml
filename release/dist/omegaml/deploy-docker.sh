#!/bin/bash
## package
##
## Deploy to docker using docker-compose
##    @script.name [option]
##

# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit

# Like `docker-compose exec` but forwarding stdin to the container
# See https://github.com/docker/compose/issues/3352
# https://stackoverflow.com/a/47591157/890242
function compose_exec() {
  local service="$1"; shift
  docker exec -i $(docker-compose ps -q $service) $@
}

pushd $script_dir

# launch and wait for services to start
docker-compose up -d
echo "Waiting for services to have initialised"
sleep 10

# apply configurations
echo "Setting up web service. Please enter admin user credentials."
docker-compose exec omegaml python manage.py loaddata landingpage.json
docker-compose exec omegaml python manage.py createsuperuser
echo "Securing mongodb"
cat scripts/mongoinit.js | compose_exec mongodb mongo

# finalize
popd