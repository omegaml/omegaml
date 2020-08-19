#!/usr/bin/env bash
# setup omegaml configs
OMEGA_BASEPATH=`python3 -c "import omegaml as om; print(om.__path__[0])"`
mkdir -p /etc/jupyter
mkdir -p /etc/ipython
mkdir -p /etc/jupyterhub
cp -r $OMEGA_BASEPATH/notebook/jupyter/* /etc/jupyter
cp -r $OMEGA_BASEPATH/notebook/jupyter/* /etc/ipython
cp -r $OMEGA_BASEPATH/notebook/jupyterhub/* /etc/jupyterhub
cp -r $OMEGA_BASEPATH/notebook/jupyterhub/*jpg /app
# setup jupyterhub user
useradd -ms /bin/bash admin
echo "admin:omegamlisfun" | chpasswd admin
usermod -a -G shadow jovyan
git clone https://github.com/jupyterhub/nativeauthenticator.git
pip3 install -e nativeauthenticator/.
# make sure the user library has been created
chown -R jovyan:users /app
chmod +x /app/scripts/omegajobs.sh
touch /app/config.yml
