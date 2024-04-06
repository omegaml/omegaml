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
dcfile=$script_dir/../docker-compose-dev.yml
curl -s --retry-all-errors --retry 5 localhost:27017 || exit 1
[ ! -f scripts/mongoinit.js ] && "cannot find scripts/mongoinit.js; see scripts/mongoinit.js.example to set up"
cat scripts/mongoinit.js | docker-compose -f $dcfile exec -T mongo mongo
