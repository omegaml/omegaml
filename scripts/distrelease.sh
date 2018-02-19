#!/bin/bash
## package
##
## Build a full distribution release including dependencies
##    @script.name [option]
##
## Options:
##    --version=VALUE   the version to build. defaults to 0.1
##    --distname=VALUE  the name of the distribution. defaults to basename 
##    --nominify        do not obfuscate code
##    --nodocker        do not build a docker image
##    --dockertag       docker image tag. defaults to basename
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
distname=${distname:=$(basename $sourcedir)}
dockertag=${dockertag:=$(basename $sourcedir)}
distdir=$script_dir/../dist
distdir=$(realpath $distdir)
version=${version:=0.1}
releasezip=$distdir/omegaml-release-$version.zip
if ! [[ -z $nominify ]]; then
  use_nominify=--nominify
fi
msgfile=$distdir/.messages

# message container
echo "[INFO] Starting build of $distname (version=$version nominify=$nominify nodocker=$nodocker)" > $msgfile

# prepare
mkdir -p $distdir
find . -name "*zip" | xargs rm -rf
find . -name "*whl" | xargs rm -rf
find . -name "*tgz" | xargs rm -rf
find . -name "*tar" | xargs rm -rf    
rm -rf $distdir/build
rm -rf $distdir/docker-staging

# build
$release $use_nominify --source .
$release $use_nominify --source ../landingpage
$release $use_nominify --source ../stackable
$release $use_nominify --source ../django-tastypie-swagger
$release $use_nominify --source ../ccbackend
$release $use_nominify --source ../tastypiex

# repackage into one zip file
pushd $distdir
unzip landingpage.zip "*whl"
unzip stackable.zip "*whl"
unzip django-tastypie-swagger.zip "*whl"
unzip ccbackend.zip "*whl"
unzip tastypiex.zip "*whl"
unzip omegaml.zip "*whl"
rm -rf ./docs
unzip omegaml.zip "docs/*"
zip -r $releasezip *whl docs
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
for d in $sourcedir/release/dist/_global_ $releasezip $sourcedir/release/dist/$distname
do
 if [[ -d $d ]]; then
   pushd $d
   zip -r $releasezip *
   popd
 fi
done
popd
echo "[INFO] Release built in $releasezip" >> $msgfile

# build docker image from release zip
if [[ -z $nodocker ]]; then
  mkdir -p $distdir/docker-staging
  pushd $distdir/docker-staging
  unzip $releasezip -d build
  pushd build
  docker images | grep omegaml | xargs | cut -f 3 -d ' ' | xargs docker rmi --force
  docker build -f Dockerfile -t $dockertag .
  popd
  popd
  echo "[INFO] Docker image $dockertag built. Source in $distdir/docker-staging/build" >> $msgfile
fi

cat $msgfile
