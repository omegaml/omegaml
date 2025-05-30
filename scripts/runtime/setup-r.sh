#!/bin/bash
## setup environment for R worker
##    @script.name [option]
##
## Options:
##    --clean     restart docker compose
##    --force     force install
##    --help      show this help message
# installs basic r packages
# https://github.com/conda-forge/r-essentials-feedstock
# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit

# install
# -- note we use miniforge/conda-forge, thus channel is conda-forge, not r
if ! which R &>/dev/null || [ "$force" ]; then
    conda install -y zlib r-essentials
fi
omegaml_dir=$(python -W ignore -c "import omegaml, pathlib as pl; print(pl.Path(omegaml.__file__).parent)")
R -f $omegaml_dir/runtimes/rsystem/install.R
