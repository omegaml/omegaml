#!/bin/bash
## package
##
## Test a built image in docker
##    @script.name [option]
##
## Options:
##   --image=VALUE  image:tag to test
##   --tags=VALUE   behave tags to run
##   --debug
##
## Required: image
# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit
source $script_dir/omutils || exit

# setup
distdir=$script_dir/../dist
builddir=$distdir/docker-staging/build
releasedir=$script_dir/../release/dist/omegaml-ee
cacert=$script_dir/../release/dist/omegaml-dev/etc/mongo/certs/ca_certificate.pem

if [ ! -z $tags ]; then
    livetest_options="--tags $tags"
fi

# establish docker env
mkdir -p $builddir
cp $releasedir/deploy-docker.sh $builddir
cp $releasedir/docker-compose.yml $builddir
echo $image
sed -i "s~omegaml/omegaml-ee:latest~$image~g" $builddir/docker-compose.yml

# test release
pushd $distdir/docker-staging/build
try ./deploy-docker.sh --clean
popd

RUNCMD="scripts/livetest.sh --url http://localhost:5000 --headless --cacert $cacert --debug $livetest_options"
echo "Will run $RUNCMD"
$RUNCMD
success=$?

echo "Stopping docker services from $distdir/docker-staging/build"
docker-compose -f $distdir/docker-staging/build/docker-compose.yml stop

echo "*** Done. Captured messages follow"
cat $msgfile
exit $success

