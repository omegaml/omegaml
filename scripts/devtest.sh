#!/usr/bin/env bash
##
## run livetests in dev
##    @script.name [option]
##

# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit

pushd $script_dir/..
nohup $script_dir/rundev.sh &
behave omegaml/tests/features -o behave.log
killall honcho

cat behave.log

