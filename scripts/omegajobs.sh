#!/bin/bash
source activate $CONDA_DEFAULT_ENV
if [[ -z `which jupyterhub` ]]; then
  conda install -y jupyterhub=0.9.4 notebook=5.7.6 tornado=6.0.1
  pip install -U jupyterhub-simplespawner==0.1 ipykernel==5.1 ipython==7.3.0
fi
CONFIGPROXY_AUTH_TOKEN=12345678 jupyterhub --port 5000 --config omegajobs/jupyterhub_config.py --debug

