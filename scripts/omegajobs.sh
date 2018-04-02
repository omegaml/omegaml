#!/bin/bash
if [[ -z `which jupyterhub` ]]; then
  conda install -y -c conda-forge jupyterhub
fi
CONFIGPROXY_AUTH_TOKEN=12345678 jupyterhub --config omegajobs/jupyterhub_config.py --debug

