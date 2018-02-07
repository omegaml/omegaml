#!/bin/bash
## package
##
## Start jupyter notebook
##    @script.name [option]
##

# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit

pushd $script_dir/../omegajobs
jupyter notebook --notebook-dir .