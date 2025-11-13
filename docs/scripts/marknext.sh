#!/bin/bash
## replaces NEXT in .rst and .py files with current VERSION
##
##    @script.name [option]
##
##    Options:
##
##    --help        show this help message
##    --tag=VALUE   the specific release tag to generate changelog for
##    --rewrite     rewrite the changelog files
##
script_dir=$(realpath "$(dirname "$0")")
source $script_dir/easyoptions || exit
src_dir=$script_dir/../..
# Read the version string once
# -- read basic version, including any -modifiers, e.g. 1.2.3-rc1
VERSION=$(head -n1 $src_dir/omegaml/VERSION)
# -- remove any modifiers, e.g. 1.2.3-rc1 => 1.2.3
VERSION=${VERSION%%-*} 
# Replace only whole‑word occurrences of “ NEXT ” in every *.rst file
echo "INFO changing > NEXT < to > $VERSION <... (may take a few minutes)"
find $src_dir/omegaml -type f -name '*.rst' -o -name '*.py' | xargs -L1 sed -i "s/\bNEXT\b/$VERSION/g"
find $src_dir/docs/source -type f -name '*.rst' -o -name '*.py' | xargs -L1 sed -i "s/\bNEXT\b/$VERSION/g"
echo "INFO Done."
