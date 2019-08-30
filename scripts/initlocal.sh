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
