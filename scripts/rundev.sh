#!/usr/bin/env bash
## package
##
## Run application from command line, optionally using docker
##    @script.name [option]
##
## To develop locally, native linux, using your local conda
##
##       $ scripts/initlocal.sh --deps --setup --install --noinit
##       $ scripts/rundev.sh --clean
##
## To develop inside docker
##
##       # build a clean env once
##       $ scripts/rundev.sh --docker --clean
##
##       # just run the container
##       $ scripts/rundev.sh --docker --shell
##
##       This will start mongodb, rabbitmq and the omegaml-dev container,
##       dropping you to an initialised shell with all packages installed.
##       The container has following directories mapped:
##
##       .. => /home/projects
##        . => /app
##        ~/.omegaml => /home/omegadev/.omegaml
##
##       This means you can use your favorite IDE to develop
##
## Options:
##      --docker        if specified uses docker to run, otherwise runs from local command line
##      --shell         if specified will invoke the shell in docker, other runs apps
##      --build         if specified builds the omegaml-dev image
##      --clean         if specified restarts the docker containers a fresh and runs initlocal
##      --cmd=VALUE     if specified passed on to shell
##      --dcfile=VALUE  if specified sets the DOCKER_COMPOSE env variable
##      --save          if specified commits state of omega-dev container to image
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
cmd=${cmd:-"scripts/rundev.sh"}

# run process
export CURRENT_USER=${CURRENT_USER:-omegadev}
export JYHUB_DEGUG=1
# task routing means the default queue is $account-default
# by enabling task routing we can have a central worker serve multiple accounts
# on separate queues
#export OMEGA_TASK_ROUTING_ENABLED=1
export OMEGA_USERID=omops
export OMEGA_APIKEY=686ae4620522e790d92009be674e3bdc0391164f
export CELERY_Q=default
export COMPOSE_FILE=${dcfile:-docker-compose.yml}

if [[ ! -z $build ]]; then
   function dobuild() {
       echo "Building $devimage"
       rm -rf $distdir
       mkdir -p $distdir
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
    cat scripts/mongoinit.js | docker-compose exec -T mongodb mongo
    docker-compose exec omegaml-dev bash -ic "scripts/initlocal.sh --setup --install"
    # save docker image state
    docker-compose ps -q omegaml-dev | xargs -I{} docker commit {} omegaml/omegaml-dev
fi

if [[ ! -z $docker ]]; then
    # if we're running in container, just run the command given
    docker-compose ps > /dev/null || bash -c "$cmd"
    docker-compose ps > /dev/null || exit 1
    # if we're running outside container, run it
    docker-compose up -d || (bash -c "$cmd")
    if [[ ! -z $shell ]]; then
        docker-compose exec omegaml-dev bash
    elif [[ ! -z $cmd ]]; then
        docker-compose exec omegaml-dev bash -ic "$cmd"
    fi
    if [[ ! -z $save ]]; then
        docker-compose ps -q omegaml-dev | xargs -I{} docker commit {} omegaml/omegaml-dev
    fi
else
    # run with local software installed
    echo "running locally"
    export DJANGO_DEBUG=1
    ./scripts/initlocal.sh --noinit
    python manage.py migrate
    python manage.py loaddata --app omegaweb landingpage
    PORT=8000 honcho start web notebook omegaops worker scheduler
fi
