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
source $script_dir/easyoptions || exit
source $script_dir/omutils || exit
pushd $script_dir

# launch and wait for services to start
if [[ ! -z $clean ]]; then
    echo "Removing services..."
    docker-compose down
fi
docker-compose up -d
echo "Waiting for services to have initialised"
countdown 45
docker-compose up -d nginx

# apply configurations
echo "Securing mongodb"
cat scripts/mongoinit.js | compose_exec mongodb mongo
echo "Setting up web service. Please enter admin user credentials."
docker-compose exec omegaml python manage.py loaddata landingpage.json
docker-compose exec omegaml python manage.py omsetupuser --username admin --email admin@omegaml.io --password test --admin --nodeploy
docker-compose exec omegaml python manage.py omsetupuser --username jyadmin --staff --apikey b7b034f57d442e605ab91f88a8936149e968e12e

# finalize
popd