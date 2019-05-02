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
##
## Required: url

# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit

pushd $script_dir/..
export LIVETEST_HEADLESS=$headless
export OMEGA_URL=$url
export OMEGA_ADMIN_USER=$user
export OMEGA_ADMIN_PASSWORD=$pass
behave ./omegaee/features --no-capture --no-capture-stderr