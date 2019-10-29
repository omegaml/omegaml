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
source $script_dir/omutils

if [[ ! -z $tags ]]; then
    behave_options="-t $tags"
fi

if [[ ! -z $headless ]]; then
   export CHROME_HEADLESS=1
fi

export OMEGA_URL=http://localhost:8000
export OMEGA_ADMIN_USER=admin@omegaml.io
export OMEGA_ADMIN_PASSWORD=test
export BEHAVE_NBFILES=$script_dir/../../omegaml-ce/docs/source/nb
export BEHAVE_DEBUG=1
export DJANGO_DEBUG=1

# start services
pushd $script_dir/..
nohup $script_dir/rundev.sh &
countdown 5
# run livetest
behave omegaee/features --no-capture $behave_options
# stop everything, keep services running in case they were already up
killall honcho

