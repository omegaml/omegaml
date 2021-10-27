#!/bin/bash
## setup environment for R worker
##    @script.name [option]
##
## Options:
##    --clean     restart docker compose
# installs basic r packages
# https://github.com/conda-forge/r-essentials-feedstock
# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit

# install
# -- note we use miniforge/conda-forge, thus channel is conda-forge, not r
conda install -y r-essentials
R -f $script_dir/../omegaml/runtimes/rsystem/install.R
