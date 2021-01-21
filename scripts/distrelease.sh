#!/bin/bash
## package
##
## Build a full distribution release including dependencies
##    @script.name [option]
##
## Options:
##    --version=VALUE   the version to build. defaults to omegaee/RELEASE
##    --distname=VALUE  the name of the distribution. defaults to basename
##    --nominify        do not obfuscate code
##    --nodocker        do not build a docker image
##    --dockertag       docker image tag. defaults to $dockertag
##    --makebase        re-create the base image
##    --nolivetest      do not run a livetest
##
##

# defaults
dockertag=${dockertag:=omegaml/omegaml-ee}
dockerbasetag=${dockerbasetag:=omegaml/omegaml-base}
distname=${distname:=omegaml-ee}

# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit
source $script_dir/omutils || exit


# setup
release=$script_dir/release.sh
sourcedir=$script_dir/..
sourcedir=$(realpath $sourcedir)
cacert=$script_dir/../release/dist/omegaml-dev/etc/mongo/certs/ca_certificate.pem

# distdir is where we stage the release files
distdir=$script_dir/../dist
mkdir -p $distdir
distdir=$(realpath $distdir)
version=${version:=$(cat $sourcedir/omegaee/RELEASE)}
# release zip is the zip file of the full release
releasezip=$distdir/omegaml-enterprise-release-$version.zip
# minify means to scramble the source code
if ! [[ -z $nominify ]]; then
  use_nominify=--nominify
fi
msgfile=$distdir/.messages

# message container
echo "[INFO] Starting build of $distname (version=$version nominify=$nominify nodocker=$nodocker)" > $msgfile

# prepare, cleanup
for fn in "*zip" "*whl" "*tgz" "*tar" "*tar.gz"
do
    find . -name $fn | xargs rm -rf
done
rm -rf $distdir/build
rm -rf $distdir/docker-staging

# clean requirements
$script_dir/consolidate-requirements.py -w pip-requirements.txt

# build
$release $use_nominify --source .
$release $use_nominify --source ../landingpage
$release $use_nominify --source ../stackable
$release $use_nominify --source ../django-tastypie-swagger
#$release $use_nominify --source ../ccbackend
$release $use_nominify --source ../tastypiex
$release $use_nominify --source ../omegaml-deploy/cloudmgr
$release $use_nominify --source ../minibatch
$release $use_nominify --source ../omegaml-ce

# repackage into one zip file
pushd $distdir
unzip landingpage.zip "*whl"
unzip stackable.zip "*whl"
unzip django-tastypie-swagger.zip "*whl"
#unzip ccbackend.zip "*whl"
unzip tastypiex.zip "*whl"
unzip omegaml.zip "*whl"
unzip minibatch.zip "*whl"
unzip omegaml-ce.zip "*whl"
unzip cloudmgr.zip "*whl"
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
cp $sourcedir/LICENSE .
cp $sourcedir/NOTICE .
cp $sourcedir/THIRDPARTY .
cp $sourcedir/manage.py .
cp -r $sourcedir/scripts .
cp -r $sourcedir/release/dist/omegaml-dev/etc/ ./etc-dev
zip $releasezip -r conda-requirements.txt requirements.txt Procfile README.rst manage.py scripts etc-dev
popd

# add distribution files
pushd $distdir
for d in $sourcedir/release/dist/_global_ $sourcedir/release/dist/$distname
do
 if [[ -d $d ]]; then
   echo "[INFO] Adding distribution files from $d" >> $msgfile
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
  docker-compose down
  docker images | grep "$dockertag" | xargs | cut -f 3 -d ' ' | xargs docker rmi --force

  if [[ ! -z $makebase ]]; then
     docker images | grep "$dockerbasetag" | xargs | cut -f 3 -d ' ' | xargs docker rmi --force
     try docker build -f Dockerfile.base -t $dockerbasetag .
  fi

  try docker build -f Dockerfile -t $dockertag:$version .
  docker tag $dockertag:$version $dockertag:latest
  popd
  popd
  echo "[INFO] Docker image $dockertag:$version built. Source in $distdir/docker-staging/build" >> $msgfile
fi

if [[ -z $nolivetest ]]; then
    # integration test release
    pushd $distdir/docker-staging/build
    try ./deploy-docker.sh --clean
    popd

    scripts/livetest.sh --url http://localhost:5000 --headless --cacert $cacert
    success=$?

    echo "Logging docker logs from $distdir/docker-staging/build"
    mkdir -p /tmp/logs
    docker-compose logs --no-color > /tmp/logs/services.log

    echo "Stopping docker services from $distdir/docker-staging/build"
    docker-compose -f $distdir/docker-staging/build/docker-compose.yml stop
fi

echo "*** Done. Captured messages follow"
cat $msgfile
exit $success
