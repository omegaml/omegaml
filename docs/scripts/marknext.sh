#!/bin/bash

# Read the version string once
# -- read basic version, including any -modifiers, e.g. 1.2.3-rc1
VERSION=$(head -n1 omegaml/VERSION)
# -- remove any modifiers, e.g. 1.2.3-rc1 => 1.2.3
VERSION=${VERSION%%-*} 
# Replace only whole‑word occurrences of “ NEXT ” in every *.rst file
echo "INFO changing > NEXT < to $VERSION... (may take a few minutes)"
find . -type f -name '*.rst' -o -name "*.py" -print0 |
xargs -0 sed -i "s/\bNEXT\b/${VERSION}/g"
echo "INFO Done."
