#!/usr/bin/env bash
# setup omegaml configs
OMEGA_BASEPATH=`python3 -c "import omegaml as om; print(om.__path__[0])"`
cp -r $OMEGA_BASEPATH/notebook/jupyter /etc/jupyter
cp -r $OMEGA_BASEPATH/notebook/jupyter /etc/ipython
cp /app/jupyterhub_config.py /srv/jupyterhub/jupyterhub_config.py
jupyter serverextension enable jupyterlab
