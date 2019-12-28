#!/bin/bash
## package
##
## Test a deployed site
##    @script.name [option]
##
## Options:
##      --url=VALUE       the OMEGA_URL as http://domain:port/
##      --user=USERID     the admin user
##      --pass=PASSWORD   the admin user password
##      --headless        if specified uses a headless browser
##      --tags=VALUE      if specified execute this tag only
##      --runlocal        if specified run omegaml-ee in docker-compose
##      --debug           if specified drops into pdb on error
##      --cacert=PEMFILE  if specified set CA_CERTS_PATH
##
## Required: url

# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit
source $script_dir/omutils || exit

if [ ! -z $tags ]; then
    behave_options="-t $tags"
fi

pushd $script_dir/..
export CHROME_HEADLESS=$headless
export OMEGA_URL=$url
export OMEGA_ADMIN_USER=$user
export OMEGA_ADMIN_PASSWORD=$pass
export BEHAVE_NBFILES=$script_dir/../../omegaml-ce/docs/source/nb
if [[ ! -z $cacert ]]; then
    export CA_CERTS_PATH=$cacert
fi

# run omega-ee
if [[ ! -z $runlocal ]]; then
    $script_dir/../release/dist/omegaml-ee/deploy-docker.sh --clean
fi

if [[ ! -z $debug ]]; then
   export BEHAVE_DEBUG=1
fi

# FIXME build a container as in core in order to test a known release
# start livetest
behave ./omegaee/features --no-capture $behave_options $LIVETEST_BEHAVE_EXTRA_OPTS
livetest_rc=$?

# stop
if [[ ! -z $runlocal ]]; then
    pushd $script_dir/../release/dist/omegaml-ee
    docker-compose down
fi

# don't swallow behave results
exit $livetest_rc