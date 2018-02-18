#!/bin/bash
## package
##
## Build a full distribution release including dependencies
##    @script.name [option]
##
## Options:
##    --version=VALUE the version to build. defaults to 0.1
##
##

# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit

# setup
release=$script_dir/release.sh
sourcedir=$script_dir/..
sourcedir=$(realpath $sourcedir)
distdir=$script_dir/../dist
distdir=$(realpath $distdir)
version=${version:=0.1}
releasezip=$distdir/omegaml-release-$version.zip

# prepare
mkdir -p $distdir
rm -rf $distdir/*.zip
rm -rf $distdir/*.whl
rm -rf $distdir/build
rm -rf $distdir/docker-staging

# build
$release --source ../omegaml
$release --source ../landingpage
$release --source ../stackable
$release --source ../django-tastypie-swagger
$release --source ../ccbackend
$release --source ../tastypiex

# repackage into one zip file
pushd $distdir
unzip landingpage.zip "*whl"
unzip stackable.zip "*whl"
unzip django-tastypie-swagger.zip "*whl"
unzip ccbackend.zip "*whl"
unzip tastypiex.zip "*whl"
unzip omegaml.zip "*whl"
zip $releasezip *whl
popd 

# add requirements and stuff
pushd $distdir
cp $sourcedir/conda-requirements.txt .
cp $sourcedir/pip-requirements.txt ./requirements.txt
cp $sourcedir/Procfile .
cp $sourcedir/README.rst .
cp $sourcedir/manage.py .
cp -r $sourcedir/scripts .
zip $releasezip -r conda-requirements.txt requirements.txt Procfile README.rst manage.py scripts
popd

# add distribution files
pushd $distdir
zip -j $releasezip $sourcedir/release/dist/* 
popd

# build docker image from release zip
mkdir -p $distdir/docker-staging
pushd $distdir/docker-staging
unzip $releasezip -d build
pushd build
docker images | grep omegaml | xargs | cut -f 3 -d ' ' | xargs docker rmi --force
docker build -f Dockerfile -t omegaml .
popd
popd
