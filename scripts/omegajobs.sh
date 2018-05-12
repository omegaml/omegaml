#!/bin/bash
if [[ -z `which jupyterhub` ]]; then
  conda install -y -c conda-forge jupyterhub=0.8.1
  pip install -U jupyterhub-simplespawner==0.1 ipykernel==4.8.2 ipython==6.2.1 notebook==5.4.1 tornado<5
fi
CONFIGPROXY_AUTH_TOKEN=12345678 jupyterhub --port 5000 --config omegajobs/jupyterhub_config.py --debug

