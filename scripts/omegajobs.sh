#!/bin/bash
## package
##
## Run jupyterhub or jupyterhub-singleuser
##
## Options:
##    --singleuser     Run jupyterhub-singleuser
##    --ip=VALUE       ip address
##    --port=PORT      port
##    --debug          debug jupyterhub and notebook
##    --label          runtime label
##
##    @script.name [option]
# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit
# set defaults
ip=${ip:-0.0.0.0}
port=${port:-5000}
debug=${debug:-$JYHUB_DEBUG}
runtimelabel="${label:-$(hostname)},$CELERY_Q"
if [[ ! -z $debug ]]; then
  jydebug="--debug"
fi
# setup environment
# TODO env vars should come from runtime/worker configmap
export C_FORCE_ROOT=1
export CELERY_Q=$runtimelabel
export OMEGA_CONFIG_FILE="$HOME/.omegaml/config.yml"
# -- running in container, use /app as a shared home
if [[ -d "/app" ]]; then
  export APPBASE="/app"
  export PYTHONPATH="$APPBASE:/app/pylib/user:/app/pylib/base"
  export PYTHONUSERBASE="/app/pylib/user"
  export PATH="$PYTHONUSERBASE/bin:$PATH"
else
  export APPBASE=$HOME
fi
# get python dependencies
get_module_basename() { python -c "import importlib;from pathlib import Path;print(Path(importlib.util.find_spec('$1').origin).parent)"; }
omegaml_dir=$(get_module_basename omegaml)
omegaee_dir=$(get_module_basename omegaee)
omegajobs_dir=$(get_module_basename omegajobs)
if [[ $singleuser ]]; then
    echo "Starting singleuser spawned juypter notebook"
    if [[ ! -f $HOME/.jupyter/.omegaml.ok ]]; then
        mkdir -p $HOME/.jupyter
        cp $omegaml_dir/notebook/jupyter/* $APPBASE/.jupyter/
        touch $HOME/.jupyter/.omegaml.ok
    fi
    # -- if there is no config file, create one
    if [[ ! -f $OMEGA_CONFIG_FILE ]]; then
        mkdir -p $OMEGA_CONFIG_FILE
        touch $OMEGA_CONFIG_FILE/config.yml
    fi
    # upgrade of jupyter hub requested
    cd $HOME
    nohup honcho -d $APPBASE start worker >> worker.log 2>&1 &
    # ensure USER_SITE exists, otherwise it is not in sys.path
    mkdir -p $(python -m site --user-site)
    if [[ ! -z $JYHUB_VERSION ]]; then
      pip install --user -U jupyterhub==$JYHUB_VERSION jupyterlab
    fi
    jupyterhub-singleuser --ip $ip --port $port --allow-root $jydebug --debug
else
    echo "Starting multiuser spawned juypter hub"
    # make sure we have the proper env setup
    # TODO move this to the runtime setup for the omegaml deployment
    pip install postgres
    cp -r $omegajobs_dir /app/pylib/base
    cp -r $omegaee_dir /app/pylib/base
    cp $omegajobs_dir/resources/logo.jpg /app/logo.jpg
    CONFIGPROXY_AUTH_TOKEN=12345678 jupyterhub --ip $ip --port $port --config $omegajobs_dir/jupyterhub_config.py $jydebug
fi

