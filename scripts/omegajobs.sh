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
# upgrade of jupyter hub requested
if [[ ! -z $JYHUB_VERSION ]]; then
  pip install -U jupyterhub==$JYHUB_VERSION jupyterlab
fi
# -- running in container, use /app as a shared home
if [[ -d "/app" ]]; then
  export APPBASE="/app"
  export PYTHONPATH="$APPBASE:/app/pylib/user:/app/pylib/base"
  export PYTHONUSERBASE="/app/pylib/user"
  export OMEGA_CONFIG_FILE="/app/pylib/user/.omegaml/config.yml"
  export PATH="$PYTHONUSERBASE/bin:$PATH"
else
  export APPBASE=$HOME
  export OMEGA_CONFIG_FILE="$APPBASE/.omegaml/config.yml"
fi
# get python dependencies
site_packages=$(python -W ignore -c "import site; print(site.getsitepackages()[0])")
omegaml_dir=$site_packages/omegaml
omegaee_dir=$site_packages/omegaee
omegajobs_dir=$site_packages/omegajobs
if [[ $singleuser ]]; then
    echo "Starting singleuser spawned juypter notebook"
    if [[ ! -f $APPBASE/.jupyter/.omegaml.ok ]]; then
        mkdir -p $APPBASE/.jupyter
        cp $omegaml_dir/notebook/jupyter/* $APPBASE/.jupyter/
        touch $APPBASE/.jupyter/.omegaml.ok
    fi
    # -- if there is no config file, create one
    if [[ ! -f $OMEGA_CONFIG_FILE ]]; then
        mkdir -p $OMEGA_CONFIG_FILE
        touch $OMEGA_CONFIG_FILE/config.yml
    fi
    cd $APPBASE/.jupyter
    nohup honcho -d $APPBASE start worker >> worker.log 2>&1 &
    # ensure USER_SITE exists, otherwise it is not in sys.path
    mkdir -p $(python -m site --user-site)
    jupyter serverextension enable jupyterlab
    jupyterhub-singleuser --ip $ip --port $port --allow-root $jydebug
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

