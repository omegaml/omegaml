#!/usr/bin/env bash
##
## run livetests in dev
##    @script.name [option]
##
##    --tags==VALUE  behave tag
##    --headless     run tests in background
##
# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit

if [[ ! -z $tags ]]; then
    behave_options="-t $tags"
fi

if [[ ! -z $headless ]]; then
   export CHROME_HEADLESS=1
fi

# force celery eager task execution
export OMEGA_LOCAL_RUNTIME=1
export BEHAVE_DEBUG=1
unset DJANGO_SETTINGS

# start services
docker-compose -f ./docker-compose-dev.yml up -d
cat $script_dir/mongoinit.js | docker exec -i omegaml-ce_mongo_1 mongo
pushd $script_dir/..
nohup $script_dir/rundev.sh &
# run livetest
behave omegaml/tests/features --no-capture $behave_options
# stop everything, keep services running in case they were already up
killall honcho

