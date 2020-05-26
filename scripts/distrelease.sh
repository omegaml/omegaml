#!/usr/bin/env bash
## package
##
## build a release docker image
##    @script.name [option]
##
## Options:
##    --distname=VALUE  the name of the distribution. defaults to basename
##    --version=VALUE   the version to build
##    --buildarg=VALUE  arg passed to docker build --build-arg
##    --push            push to dockerhub
# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit
source $script_dir/omutils || exit

imagename="omegaml/$distname:$version"
imagename_latest="omegaml/$distname:latest"
builddir=build
distdir=dist/staging/$distname
srcdir=scripts/docker/$distname
runtime_scripts=scripts/runtime

if [[ ! -z $buildarg ]]; then
    buildarg="--build-arg $buildarg"
fi

# copy files to staging
rm -rf $builddir
rm -rf $distdir
mkdir -p $distdir
mkdir -p $distdir/scripts
cp -r $srcdir/* $distdir
cp $runtime_scripts/* $distdir/scripts
cp dist/*whl $distdir/packages
# build and push
cd $distdir && docker build $buildarg -t $imagename .
docker tag $imagename $imagename_latest
if [[ ! -z $push ]]; then
  docker push $imagename
fi
echo "image $imagename built in $distdir and pushed"
