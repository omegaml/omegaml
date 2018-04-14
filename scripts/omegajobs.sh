#!/bin/bash
if [[ -z `which jupyterhub` ]]; then
  conda install -y -c conda-forge jupyterhub
  pip install jupyterhub-simplespawner==0.1
fi
CONFIGPROXY_AUTH_TOKEN=12345678 jupyterhub --port 5000 --config omegajobs/jupyterhub_config.py --debug

