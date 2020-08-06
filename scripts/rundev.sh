#!/usr/bin/env bash
## package
##
## Run application from command line, optionally using docker
##    @script.name [option]
##
## Options:
##      --docker     if specified uses docker to run, otherwise runs from local command line
##      --shell      if specified will invoke the shell in docker, other runs apps
##      --build      if specified builds the omegaml-dev image
##      --clean      if specified restarts the docker containers a fresh and runs initlocal
# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit
source $script_dir/omutils || exit

# set script arguments
devimage=omegaml/omegaml-dev
chromedriverbin=`which chromedriver`
distdir=./dist/omegaml-dev
host_user=omegadev
host_uid=$(id -u)
host_guid=$(id -g)
container_uid=$host_uid:$host_guid

# run process
export CURRENT_UID=$container_uid
export CURRENT_USER=$host_user
# task routing means the default queue is $account-default
# by enabling task routing we can have a central worker serve multiple accounts
# on separate queues
#export OMEGA_TASK_ROUTING_ENABLED=1
export CELERY_Q=default
#export OMEGA_USERID=omops
#export OMEGA_APIKEY=686ae4620522e790d92009be674e3bdc0391164f

if [[ ! -z $build ]]; then
   function dobuild() {
       echo "Building $devimage"
       rm -rf $distdir
       mkdir -p $distdir
       cp *requirements* $distdir
       cp Dockerfile.dev $distdir
       cp -r ./release/dist/omegaml-dev/. $distdir
       cp -r ./scripts $distdir
       pushd $distdir
       # https://stackoverflow.com/a/50362562/890242
       build_args="--build-arg UNAME=$host_user --build-arg UID=$host_uid --build-arg GID=$host_guid"
       docker build $build_args  --no-cache -t $devimage -f Dockerfile.dev .
       popd
       echo "Run application using scripts/rundev.sh --docker"
       echo "Run shell using scripts/rundev.sh --docker --shell"
   }
   dobuild
   exit 0
fi


if [[ ! -z $clean ]]; then
    docker-compose down
    docker-compose up -d --remove-orphans
    waiton "waiting for mongodb" http://localhost:27017
    cat scripts/mongoinit.js | docker exec -i omegaml_mongodb_1 mongo
    docker-compose exec omegaml-dev bash -ic "scripts/initlocal.sh --install"
fi

if [[ ! -z $docker ]]; then
    docker-compose up -d
    if [[ ! -z $shell ]]; then
        docker-compose exec omegaml-dev bash
    else
        docker-compose exec omegaml-dev bash -ic "scripts/rundev.sh"
    fi
else
    # run with local software installed
    export DJANGO_DEBUG=1
    python manage.py migrate
    python manage.py loaddata landingpage.json
    PORT=8000 honcho start web worker notebook scheduler omegaops
fi
