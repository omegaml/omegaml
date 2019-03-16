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
##
## Required: url

# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit

pushd $script_dir/..
OMEGA_URL=$url USER=$user PASSWORD=$pass behave ./features