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
#export OMEGA_APIUSER=omops
#export OMEGA_APIKEY=686ae4620522e790d92009be674e3bdc0391164f
export OMEGA_FRAMEWORKS="scikit-learn,tensorflow,keras,dash"
# use old style notebook
export JY_DEFAULT_URL="/tree"
export BEHAVE_NBFILES=$script_dir/../../omegaml-ce/docs/source/nb
export BEHAVE_DEBUG=1
export DJANGO_DEBUG=1

# start services
pushd $script_dir/..
nohup $script_dir/rundev.sh &
waiton "Waiting for services to have initialised" $OMEGA_URL
echo "Starting tests..."
# run livetest
# -- using bash -c to avoid removal of quotes in $BEHAVE_ARGS, in particular the --tags argument
#    this way we can pass BEHAVE_ARGS='--tags="<expression>"'
bash -c "behave omegaee/features --no-capture $behave_options $BEHAVE_ARGS"
echo "DONE"
# stop everything, keep services running in case they were already up
killall honcho

