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

devimage=omegaml/omegaml-dev
chromedriverbin=`which chromedriver`
distdir=./dist/omegaml-dev

if [[ ! -z $build ]]; then
   echo "Building $devimage"
   rm -rf $distdir
   mkdir -p $distdir
   cp *requirements* $distdir
   cp Dockerfile.dev $distdir
   cp -r ./release/dist/omegaml-dev/. $distdir
   if [[ -f $chromedriverbin ]]; then
      cp $chromedriverbin $distdir
   else
      echo "WARNING Missing $chromedriverbin. You won't be able to run livetests"
      echo "WARNING Install chromedriver from https://sites.google.com/a/chromium.org/chromedriver/downloads"
   fi
   pushd $distdir
   docker build -t $devimage -f Dockerfile.dev .
   popd
   echo "Run application using scripts/rundev.sh --docker"
   echo "Run shell using scripts/rundev.sh --docker --shell"
   exit 0
fi

if [[ ! -z $clean ]]; then
    docker-compose -f docker-compose-dev.yml down
    docker-compose -f docker-compose-dev.yml up -d --remove-orphans
    cat scripts/mongoinit.js | docker exec -i omegaml_mongo_1 mongo
    docker-compose -f docker-compose-dev.yml exec omegaml-dev scripts/initlocal.sh
fi

if [[ ! -z $docker ]]; then
    docker-compose -f docker-compose-dev.yml up -d
    if [[ ! -z $shell ]]; then
        docker-compose -f docker-compose-dev.yml exec omegaml-dev bash
    else
        docker-compose -f docker-compose-dev.yml exec omegaml-dev scripts/rundev.sh
    fi
else
    # run with local software installed
    omegamlcore_dir=../omegaml-ce
    omegamlcore_scripts_dir=$omegamlcore_dir/scripts
    export DJANGO_DEBUG=1
    python manage.py migrate
    PORT=8000 honcho start web worker notebook
fi