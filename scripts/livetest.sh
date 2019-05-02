#!/bin/bash
## package
##
## Test omegaml package from live omegaml image and omegaml pypi package
##    @script.name [option]
##
## Options:
##      --build           if specified rebuilds the omegaml image
##      --local           if specified uses local dist package
##      --testpypi        if specified uses test pypi
##

# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit

mongourl="mongodb://mongodb:27017/omega"
docker_network="--network omegaml-ce_default"
docker_env="-e OMEGA_MONGO_URL=$mongourl"
docker_image="omegaml/livetest"
behave_features="/usr/local/lib/python3.6/site-packages/omegaml/tests/features"

if [ "$testpypi" == "yes" ]; then
   pypi="https://test.pypi.org/simple/"
else
   pypi="https://pypi.org/simple/"
fi

if [ "$build" == "yes" ]; then
   buildopt="--build"
fi

if [ "$local" == "yes" ]; then
   mkdir -p $script_dir/livetest/packages
   cp $script_dir/../dist/*whl $script_dir/livetest/packages
fi

pushd $script_dir/..
docker-compose down
docker-compose up $buildopt -d
docker rmi -f omegaml/livetest
docker build --build-arg pypi=$pypi -f ./scripts/livetest/Dockerfile -t omegaml/livetest $script_dir/livetest
docker run $docker_network $docker_env $docker_image behave $behave_features
rm -f $script_dir/livetest/packages/*whl
docker-compose down
