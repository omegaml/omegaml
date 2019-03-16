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
##      --nominify           if set no code obfuscation is applied
##

# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit

# setup basic directories
mkdir -p dist
mkdir -p build

# script configuration
sourcedir=${source:=.}
sourcedir=$(realpath $source)
release=${release:=$(basename $sourcedir)}
releasefilesdir=$script_dir/../release/
headerfqn=${header:=$releasefilesdir/source/COPYRIGHT}
headerfqn=$(realpath $headerfqn)
distdir=$script_dir/../dist
distdir=$(realpath $distdir)

# execute
setup() {
    rm -rf $distdir/releasezip
    rm -rf $distdir/$release
    rm -rf $distdir/releasezip/docs
    mkdir -p $distdir/releasezip
    mkdir -p $distdir/$release
    mkdir -p $distdir/releasezip/docs
}

build_sdist () {
    # -- build a source distribution as the basis for obfuscation
    pushd $sourcedir
    PYTHONPATH=$sourcedir:$PYTHONPATH python setup.py sdist
    # 1. copy all code into a safe place
    tar --exclude-vcs -czf $distdir/$release.tgz .
    popd
    # -- unpack distbuild
    pushd $distdir/$release
    tar --exclude-vcs -xzf $distdir/$release.tgz
    popd
}


obfuscate () {
    # 2. obfuscate and prepend header file on each file
    pushd $distdir/$release
    # -- build a script, then execute
    find . -name "*py" | xargs -L1 -I{} echo "echo Minify {} && pyminifier -o {}_pym --gzip {} && cat $headerfqn {}_pym > {} && rm {}_pym"  > obfuscate.sh
    chmod +x obfuscate.sh && obfuscate.sh
    popd
}

build_wheel () {
    # 3. build actual package
    pushd $distdir/$release
    PYTHONPATH=$sourcedir:$PYTHONPATH python setup.py bdist_wheel
    cp dist/*whl $distdir
    popd
}


build_docs() {
   # build documentation
   pushd docs
   make html
   popd
   for d in docs/build/html docs/_build/html
   do
      if [[ -d $d ]]; then
        pushd $d
        cp -r * $distdir/releasezip/docs
        popd
      fi
   done
}


build_release() {
    # 4. build release zip
    for d in _global_ $release
    do
      if [[ -d $releasefilesdir/dist/$d ]]; then
        pushd $releasefilesdir/dist/$d
        cp -r * $distdir/releasezip/.
        popd
      fi
    done
    pushd $distdir/releasezip
    mv ../*whl .
    zip -r $release.zip *
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
if [[ -z $nominify ]]; then
  obfuscate
fi
build_wheel
if [[ -d $sourcedir/docs ]]; then
  build_docs
fi
build_release
finalize
clean
popd
