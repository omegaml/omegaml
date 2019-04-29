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
  conda install -y -c conda-forge jupyterhub
  pip install -U jupyterhub-simplespawner==0.1 ipykernel==4.8.2 ipython==6.2.1
  pip install -U notebook==5.4.1
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
    # kubespanwer pulls in kubernetes==6.*, but we use 8.* for paasdeploy
    # -- thus we only install kubespawner on omjobs, not in the spawned process
    pip install -U jupyterhub-kubespawner==0.9.0
    CONFIGPROXY_AUTH_TOKEN=12345678 jupyterhub --ip $ip --port $port --config omegajobs/jupyterhub_config.py --debug
fi

