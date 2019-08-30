#!/bin/bash
## package
##
## Initialize a local deployment
##    @script.name [option]
##
## Options:
##

# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit

cat scripts/mongoinit.js | docker exec -i omegaml_mongo_1 mongo
python manage.py migrate
python manage.py loaddata landingpage.json
python manage.py omsetupuser --username admin --email admin@omegaml.io --password test --admin --nodeploy
python manage.py omsetupuser --username jyadmin --staff --apikey b7b034f57d442e605ab91f88a8936149e968e12e
