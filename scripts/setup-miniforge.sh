#!/bin/bash
## package
##
## Initialize a local deployment
##    @script.name [option]
##
## Options:
##
set -e
# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit
source $script_dir/omutils

# use a version that is at least 30 days old to ensure we have a vulunerability cooldown period
# --version and sha from https://github.com/conda-forge/miniforge/releases
MINIFORGE_VERSION=26.1.1-2
MINIFORGE_VERSION_SHA256=sha256:831421c1f32d8b510e0ef7f261aaabdbf567bdbba37373432d492621b824ab1f
MINIFORGE_SCRIPT=Miniforge3-Linux-x86_64.sh

function setup() {
    # see https://github.com/conda-forge/miniforge
    echo "Downloading $MINIFORGE_VERSION $MINIFORGE_SCRIPT"
    curl -L -O --silent --show-error "https://github.com/conda-forge/miniforge/releases/download/$MINIFORGE_VERSION/$MINIFORGE_SCRIPT"
    echo "Verifying sha256 of $MINIFORGE_SCRIPT"
    VERSION_HASH=$(echo $MINIFORGE_VERSION_SHA256 | sed 's/^sha256://')
    echo "$VERSION_HASH $MINIFORGE_SCRIPT" | sha256sum --check || { echo "checksum mismatch"; exit 2; }
    echo "Run installation $MINIFORGE_SCRIPT"
    bash $MINIFORGE_SCRIPT -b -p "$HOME/miniforge3"
    echo "Setting up conda environment"
    cat ~/miniforge3/etc/profile.d/conda.sh >> ~/.bashrc
    activate_conda
    # update using the classic solver due to https://github.com/conda/conda-libmamba-solver/issues/635
    conda update -y -n base -c conda-forge conda conda-libmamba-solver --solver classic
    # avoid installing packages newer than 7 days ago
    pip config set global.uploaded_prior_to "$(date -d '7 days ago' -Iseconds --utc)" >/dev/null || true
}

setup