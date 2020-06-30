#!/usr/bin/env bash
# setup omegaml configs
OMEGA_BASEPATH=`python3 -c "import omegaml as om; print(om.__path__[0])"`
mkdir -p /etc/jupyter
mkdir -p /etc/ipython
cp -r $OMEGA_BASEPATH/notebook/jupyter/* /etc/jupyter
cp -r $OMEGA_BASEPATH/notebook/jupyter/* /etc/ipython
chmod +x /app/scripts/omegajobs.sh
touch /app/config.yml
