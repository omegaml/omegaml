#!/bin/bash
## generates changelog files for each release tag by querying the github API
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
BASE_DIR=$(realpath "$script_dir/..")
RELEASE_PATTERNS=${tag:-"release/[02].[0-9]+(.[0-9]+)?$"}
RELEASES=$(git tag | grep -E "$RELEASE_PATTERNS" | xargs)
CHANGES_DIR=$BASE_DIR/source/changes
PACKAGE_DIR=$(realpath $BASE_DIR/../omegaml)
VERSION=$(cat $PACKAGE_DIR/VERSION)

# replace "next" version inside sphinx tags in rst, md and py files
# - .. versionadded:: next => .. versionadded/:: <version>
# - .. versionchanged:: next => .. versionchanged/:: <version>
function update_next_release()
{
  echo "INFO Updating 'next' version strings for releases matching $RELEASE_PATTERNS"
  CHANGE_TAGS="versionadded versionchanged"
  EXTS="\.(rst|md|py)$"
  set -x
  for tag in $CHANGE_TAGS; do
    find $PACKAGE_DIR | grep -E $EXTS | xargs -I {} sed -i "s/\.\. $tag:: next/.. $tag:: $VERSION/g" {}
  done
}

function generate_changes()
{
  echo "INFO Generating changelogs for releases matching $RELEASE_PATTERNS"
  for release in $(sort_semver $RELEASES); do
    # prepare md and rst filenames
    changefn_base="$CHANGES_DIR/v${release/release\//}"
    changefn_md=$changefn_base.md
    changefn_rst=$changefn_base.rst
    release_dt=$(git show -s --format="%ci" "$release" | cut -d ' ' -f 1)
    if [ -f $changefn_rst ] && [ -z "$rewrite" ]; then
      echo "INFO Skipping $changefn ($release)"
      prev_release=$release
      continue
    fi
    # get changelog from github release
    echo "INFO Writing $changefn_rst ($release)"
    echo "# Release notes $release" > $changefn_md
    echo " " >> $changefn_md
    echo "Released $release_dt" >> $changefn_md
    echo " " >> $changefn_md
    gh release view $release | grep --no-group-separator -A 999 '\-\-' >> $changefn_md
    $script_dir/git-rln.sh ${prev_release:-$release^} $release >> $changefn_md
    # convert md to rst
    sed -i s/^\-\-$// $changefn_md
    pandoc -f markdown -t rst $changefn_md -o $changefn_rst
    # clean up
    rm $changefn_md
    prev_release=$release
  done
}

# Function to sort semantic versions from earliest to latest, with optional tags
sort_semver() {
    local versions=("$@")

    # Function to extract the version from a tag (if present)
    extract_version() {
        local tag="$1"
        # Extract version from tag using regex, or use the whole string if not a tag
        if [[ "$tag" =~ ^release/(.*)$ ]]; then
            echo "${BASH_REMATCH[1]}"
        else
            echo "$tag"
        fi
    }

    # Function to convert version to an integer for comparison
    version_to_int() {
        local version="$1"
        # Replace periods with spaces and pad each part with leading zeros to ensure proper numeric sorting
        printf "%04d%04d%04d\n" $(echo "$version" | tr '.' ' ' | awk '{printf "%d %d %d", $1, $2, $3}')
    }

    # Extract versions and convert to a sortable format
    for tag in "${versions[@]}"; do
        version=$(extract_version "$tag")
        echo "$(version_to_int "$version") $tag"
    done | sort -n | awk '{print $2}'
}

update_next_release
generate_changes

