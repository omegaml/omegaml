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

pushd $script_dir/..
python manage.py collectstatic --noinput --no-post-process
echo  "waiting for mysql & mongo db to be up and running..."
sleep 30
python manage.py migrate
honcho start web
