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
python manage.py collectstatic --noinput
python manage.py migrate
honcho start web
