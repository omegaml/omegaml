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
omegaml_dir=$(python -W ignore -c  "import omegaml; print(omegaml.__path__[0])")
omegajobs_dir=$(python -W ignore -c  "import omegajobs; print(omegajobs.__path__[0])")
runtimelabel="${label:-$(hostname)},$CELERY_Q"


if [[ ! -z $debug ]]; then
  jydebug="--debug"
fi

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

if [[ $singleuser ]]; then
    echo "Starting singleuser spawned juypter notebook"
    if [[ ! -f $HOME/.jupyter/.omegaml ]]; then
        mkdir -p $HOME/.jupyter
        cp $omegaml_dir/notebook/jupyter/* $HOME/.jupyter/
    fi
    # -- if there is no config file, create one
    if [[ ! -f $OMEGA_CONFIG_FILE ]]; then
        mkdir -p $OMEGA_CONFIG_FILE
        touch $OMEGA_CONFIG_FILE/config.yml
    fi
    pip install -U jupyterhub==$JY_HUB_VERSION jupyterlab
    cd $HOME/.jupyter
    nohup honcho -d $APPBASE start worker >> worker.log 2>&1 &
    jupyter serverextension enable jupyterlab
    jupyterhub-singleuser --ip $ip --port $port --allow-root $jydebug
else
    echo "Starting multiuser spawned juypter hub"
    # make sure we have the proper env setup
    # TODO move this to the runtime setup for the omegaml deployment
    pip install postgres
    image_pysite=$(find / -name omegajobs | grep site-packages)/..
    cp -r $image_pysite/omegajobs /app/pylib/base
    cp -r $image_pysite/omegaee /app/pylib/base
    CONFIGPROXY_AUTH_TOKEN=12345678 jupyterhub --ip $ip --port $port --config $omegajobs_dir/jupyterhub_config.py $jydebug
fi

