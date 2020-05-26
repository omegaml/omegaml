#!/bin/bash
## package
##
## Run jupyterhub or jupyterhub-singleuser
##
## Options:
##    --singleuser     Run jupyterhub-singleuser
##    --ip=VALUE       ip address
##    --port=PORT      port
##    --label          runtime label
##    --debug          debug jupyterhub and notebook
##
##    @script.name [option]
# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit
# set defaults
ip=${ip:-0.0.0.0}
port=${port:-5000}
omegaml_dir=$(python -W ignore -c  "import omegaml; print(omegaml.__path__[0])")
runtimelabel=${label:-$(hostname)}
if [[ ! -z $debug ]]; then
  jydebug="--debug"
fi
# setup environment
# TODO env vars should come from runtime/worker configmap
export C_FORCE_ROOT=1
export CELERY_Q=$runtimelabel
# -- running in pod, use /app as a shared home
if [[ -d "/app" ]]; then
  export APPBASE="/app"
  export PYTHONPATH="/app/pylib/user:/app/pylib/base"
  export PYTHONUSERBASE="/app/pylib/user"
  export OMEGA_CONFIG_FILE="app/pylib/user/.omegaml/config.yml"
  export PATH="$PYTHONUSERBASE/bin:$PATH"
else
  export APPBASE=$HOME
  export OMEGA_CONFIG_FILE="$APPBASE/.omegaml/config.yml"
fi
if [[ ! -f $HOME/.jupyter/.omegaml ]]; then
    mkdir -p $HOME/.jupyter
    cp $omegaml_dir/notebook/jupyter/* $HOME/.jupyter/
fi
# -- if there is no config file, create one
if [[ ! -f $OMEGA_CONFIG_FILE ]]; then
    mkdir -p $OMEGA_CONFIG_FILE
    touch $OMEGA_CONFIG_FILE/config.yml
fi
# -- start worker and jupyterhub
pip install -U --user jupyterhub==$JY_HUB_VERSION jupyterlab
cd $HOME/.jupyter
nohup honcho -d $APPBASE start worker >> worker.log 2>&1 &
jupyterhub-singleuser --ip $ip --port $port $jydebug
