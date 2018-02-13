#!/bin/bash
## package
##
## Build a full distribution release including dependencies
##    @script.name [option]
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

# prepare
rm -rf $distdir/*.zip
rm -rf $distdir/build

# build
$release --source ../omegaml
$release --source ../landingpage
$release --source ../stackable
$release --source ../django-tastypie-swagger
$release --source ../ccbackend

# repackage into one zip file
pushd $distdir
unzip landingpage.zip "*whl"
unzip stackable.zip "*whl"
unzip django-tastypie-swagger.zip "*whl"
unzip ccbackend.zip "*whl"
zip omegaml.zip *whl
popd 

# add requirements and stuff
pushd $distdir
cp $sourcedir/conda-requirements.txt $distdir
cp $sourcedir/requirements.txt $distdir
cp $sourcedir/Procfile $distdir
cp $sourcedir/README.rst $distdir
cp $sourcedir/manage.py $distdir
zip omegaml.zip conda-requirements.txt requirements.txt Procfile README.rst manage.py
popd

# add distribution files
pushd $distdir
zip -j omegaml.zip $sourcedir/release/dist/* 
popd

# build docker image
pushd $distdir
unzip omegaml.zip -d build
pushd build
docker build -f Dockerfile -t omegaml .
popd
popd
