#!/bin/bash
## package
##
## Build a release
##    @script.name [option]
##
## Options:
##      --release=VALUE      the release name
##      --header=VALUE       the path to the header inserted into python files
##      --source=VALUE       the path to the source, defaults to the current directory
##

# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit

# script configuration
sourcedir=${source:=.}
sourcedir=$(realpath $source)
release=${distname:=$(basename $(realpath $sourcedir))}
releasefilesdir=$script_dir/../release/
headerfqn=${header:=$releasefilesdir/source/COPYRIGHT}
headerfqn=$(realpath $headerfqn)
distdir=$script_dir/../dist
distdir=$(realpath $distdir)


# execute
setup() {
    rm -rf $distdir/releasezip
    mkdir -p $distdir/releasezip
}

build_sdist () {
    # -- build a source distribution as the basis for obfuscation
    PYTHONPATH=$script_dir/..:$PYTHONPATH python setup.py sdist
    # -- obfuscate all python code
    # 1. copy all code into a safe place
    rm -rf $distdir/$release
    mkdir -p $distdir/$release
    tar -czf $distdir/$release.tgz .
}


obfuscate () {
    # 2. obfuscate and prepend header file on each file
    pushd $distdir/$release
    tar -xzf ../$release.tgz 
    # -- build a script, then execute
    find . -name "*py" | xargs -L1 -I{} echo "echo Minify {} && pyminifier -o {}_pym --gzip {} && cat $headerfqn {}_pym > {} && rm {}_pym"  > obfuscate.sh
    chmod +x obfuscate.sh && obfuscate.sh
    popd
}

build_wheel () {
    # 3. build actual package
    pushd $distdir/$release
    PYTHONPATH=$script_dir/..:$PYTHONPATH python setup.py bdist_wheel
    cp dist/*whl $distdir
    popd
}


build_docs() {
   # build documentation
   pushd docs
   make html
   popd
   pushd docs/build/html
   mkdir -p $distdir/releasezip/docs
   cp -r * $distdir/releasezip/docs
   popd
}


build_release() {
    # 4. build release zip
    pushd $releasefilesdir/dist
    cp -r * $distdir/releasezip/.
    pushd $distdir/releasezip
    mv ../*whl .
    zip -r $release.zip *
    popd
    popd
}

finalize() {
    # 5. move files into the right place
    mv $distdir/releasezip/$release.zip $distdir/$release.zip
}

clean () {
    # 5. clean up
    rm -rf $distdir/$release
    rm -rf $distdir/releasezip
}

pushd $sourcedir
setup
build_sdist
obfuscate
build_wheel
if [[ -d $sourcedir/docs ]]; then
  build_docs
fi
build_release
finalize
clean
popd
