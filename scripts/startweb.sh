#!/bin/bash
## package
##
## Start omegaml web
##    @script.name [option]
##

# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit
source $script_dir/omutils || exit

MONGO_SERVICE_HOST=${MONGO_SERVICE_HOST:-${MONGODB_SERVICE_HOST:-localhost}:${MONGODB_SERVICE_PORT:-27017}}
MONGO_HTTP_URL=${MONGO_HTTP_URL:-http://$MONGO_SERVICE_HOST}

pushd $script_dir/..
python manage.py collectstatic --noinput
waiton "waiting for mongodb" $MONGO_HTTP_URL
python manage.py migrate
honcho start web
