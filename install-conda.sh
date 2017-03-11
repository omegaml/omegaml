#!/bin/bash
CONDA_DIR=$HOME/.omegaml/miniconda
wget https://repo.continuum.io/miniconda/Miniconda2-latest-Linux-x86_64.sh
chmod +x Miniconda2-latest-Linux-x86_64.sh
./Miniconda2-latest-Linux-x86_64.sh -b -p $CONDA_DIR
echo "PATH=$CONDA_DIR:\$PATH" >> $HOME/.bashrc
export PATH=$CONDA_DIR:$PATH
conda install --file conda-requirements.txt
conda env list

