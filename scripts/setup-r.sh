#!/bin/bash
## setup environment for R worker inside omegaee built image
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
# -- https://github.com/rstudio/reticulate/issues/1213
export RETICULATE_MINICONDA_ENABLED=0
export RETICULATE_PYTHON=$(which python)
omegaml_dir=$(python -c "import omegaml, pathlib as pl; print(pl.Path(omegaml.__file__).parent)")
R -f $omegaml_dir/runtimes/rsystem/install.R
