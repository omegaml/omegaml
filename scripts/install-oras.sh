#!/bin/bash
## package
##
## Install oras for oci repository support
##    @script.name [option]
##
## Options:
##

# adopted from https://oras.land/docs/installation
OS="$(uname -s | tr A-Z a-z)"
ARCH=$(uname -m | sed -e 's/x86_64/amd64/g')
VERSION="1.3.0"
curl -LO "https://github.com/oras-project/oras/releases/download/v${VERSION}/oras_${VERSION}_${OS}_${ARCH}.tar.gz"
mkdir -p oras-install/
tar -zxf oras_${VERSION}_${OS}_${ARCH}.tar.gz -C oras-install/
chmod +x oras-install/oras
mkdir "-p" $HOME/.local/bin
mv oras-install/oras $HOME/.local/bin
rm -rf oras-install oras_${VERSION}_${OS}_${ARCH}.tar.gz
echo "INFO oras installed to $HOME/.local/bin"
