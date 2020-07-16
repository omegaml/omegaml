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
export BEHAVE_DEBUG=1
export OMEGA_MONGO_URL=mongodb://admin:foobar@localhost:27017/omega
unset DJANGO_SETTINGS

# start services
pushd $script_dir/..
nohup $script_dir/rundev.sh &
sleep 15
# run livetest
behave omegaml/tests/features --no-capture $behave_options
# stop everything, keep services running in case they were already up
killall honcho

