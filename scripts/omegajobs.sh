#!/bin/bash
## package
##
## Run jupyterhub or jupyterhub-singleuser
##
## Options:
##    --singleuser     Run jupyterhub-singleuser
##    --ip=VALUE       ip address
##    --port=PORT      port
##    --installonly    install only then exit
##
##    @script.name [option]

# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit

ip=${ip:=0.0.0.0}
port=${port:=5000}

if [[ -z `which jupyterhub` || $installonly ]]; then
  echo  "Installing jupyterhub"
  conda install -y -c conda-forge jupyterhub=0.9.4 notebook=5.7.6
  pip install -U jupyterhub-simplespawner==0.1 ipykernel==5.1 ipython==7.3.0
  if [[ $installonly ]]; then
    echo "Installation completed. Not starting at this time due to --installonly."
    exit
  fi
fi

if [[ $singleuser ]]; then
    echo "Starting singleuser spawned juypter notebook"
    mkdir -p $HOME/.jupyter
    cp -r /opt/conda/lib/python3.6/site-packages/omegaml/notebook/jupyter/* $HOME/.jupyter/
    cd $HOME/.jupyter
    jupyterhub-singleuser --ip $ip --port $port --debug --allow-root
else
    echo "Starting multiuser spawned juypter hub"
    # -- we only need & install kubespawner on omjobs, not in the spawned process
    pip install -U jupyterhub-kubespawner==0.10.1
    sitepackages=$(python -m site | grep site-packages | head -n 1 | cut -f 2 -d "'")
    CONFIGPROXY_AUTH_TOKEN=12345678 jupyterhub --ip $ip --port $port --config $sitepackages/omegajobs/jupyterhub_config.py --debug
fi

