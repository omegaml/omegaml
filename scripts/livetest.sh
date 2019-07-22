#!/bin/bash
## package
##
## Test omegaml package from live omegaml image and omegaml pypi package
##    @script.name [option]
##
## Options:
##      --build           if specified rebuilds the omegaml image
##      --nobuild         if specified does not build omegaml nor livetest image
##      --local           if specified uses local dist package
##      --testpypi        if specified uses test pypi
##      --tag=VALUE       tag for omegaml image (only with --build)
##      --headless        if specified runs chrome headless
##
# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit
# configuration specific to the environment
mongourl="mongodb://mongodb:27017/omega"
omegaurl="http://omegaml:5000"
jupyterurl="http://omegaml:8888"
# from here on should be all standard
docker_network="--network omegaml-ce_default"
docker_env="-e OMEGA_MONGO_URL=$mongourl -e OMEGA_URL=$omegaurl -e JUPYTER_URL=$jupyterurl"
docker_image="omegaml/livetest"
behave_features="/usr/local/lib/python3.7/site-packages/omegaml/tests/features"
chrome_debug_port="9222:9222/tcp"
docker_tag=$(cat omegaml/VERSION)
docker_tag=${tag:-$docker_tag}
# set pypi to use
if [ "$testpypi" == "yes" ]; then
   pypi="https://test.pypi.org/simple/"
else
   pypi="https://pypi.org/simple/"
fi
# copy local dist packages instead of using pypi if requested
if [ "$local" == "yes" ]; then
   mkdir -p $script_dir/livetest/packages
   cp $script_dir/../dist/*whl $script_dir/livetest/packages
fi
# build omegaml image if requested
if [ "$build" == "yes" ]; then
   buildopt="--build"
   docker-compose down --rmi local
fi
# prepare to run
pushd $script_dir/..
mkdir -p /tmp/screenshots
# only build livetet image if requested
if [ -z "$nobuild" ]; then
  docker rmi -f $docker_image
  docker build --build-arg pypi=$pypi -f ./scripts/livetest/Dockerfile -t $docker_image $script_dir/livetest
fi
# get omegaml running, build if requested
docker-compose stop
docker-compose up $buildopt -d
# tag the built image
if [ ! -z "$tag" ]; then
  docker tag omegaml/omegaml:latest omegaml/omegaml:$docker_tag
fi
# actually run the livetest
docker run -p $chrome_debug_port -e CHROME_HEADLESS=1 -e CHROME_SCREENSHOTS=/tmp/screenshots -v /tmp/screenshots:/tmp/screenshots $docker_network $docker_env $docker_image behave --no-capture $behave_features
#docker run -it -p $chrome_debug_port -e CHROME_HEADLESS=1 -e CHROME_SCREENSHOTS=/tmp/screenshots -v /tmp/screenshots:/tmp/screenshots $docker_network $docker_env $docker_image bash
rm -f $script_dir/livetest/packages/*whl
docker-compose stop
