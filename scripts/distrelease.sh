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
##    --pyver=VALUE     the python version for the livetest image, defaults to current python version
##    --push            push to dockerhub
# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit
source $script_dir/omutils || exit

builddir=build
distdir=dist/staging/$distname
srcdir=scripts/docker/$distname
runtime_scripts=scripts/runtime
pyver=${pyver:-$(python --version | cut -d' ' -f2 | cut -d'.' -f1-2)}
imagename="omegaml/$distname:$version-$pyver"
imagename_latest="omegaml/$distname:latest"

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
pushd $distdir
docker build $buildarg --build-arg pyver=$pyver -t $imagename .
popd
docker tag $imagename $imagename_latest
if [[ ! -z $push ]]; then
  docker push $imagename
fi
echo "image $imagename built in $distdir and pushed"
