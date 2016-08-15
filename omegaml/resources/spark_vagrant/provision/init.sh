#!/bin/bash
# install packages
HOME="/home/vagrant"
VAGRANT_VOL="/vagrant"
##
# copy over necessary files
##
cp $VAGRANT_VOL/provision/supervisord.conf.ubuntu $HOME/supervisord.conf
cp $VAGRANT_VOL/provision/ipython_notebook_config.py $HOME/.ipython/profile_pyspark/.
# check if omegaml is installed
# if installed reinstall
$HOME/anaconda/bin/pip freeze | grep ^omegaml
if [[ $? -eq 0 ]]; then
    $HOME/anaconda/bin/pip uninstall -y omegaml
fi
# install packages
$HOME/anaconda/bin/pip install --process-dependency-links -r /vagrant/provision/requirements.txt
# cleanup
rm -rf $HOME/.cache
##
# reads env vars passed in through vagrant and set them up for use
##

env_vars="OMEGA_MONGO_URL OMEGA_BROKER"
for env_var in $env_vars; do
    if [[ -n ${!env_var} ]]; then
        echo "export $env_var=${!env_var}" >> .bashrc
    fi
done

##
# Start Spark
##
$HOME/spark/sbin/start-all.sh
echo "Formatting namenode"
$HOME/hadoop/bin/hdfs namenode -format -force
$HOME/hadoop/sbin/start-dfs.sh
$HOME/hadoop/sbin/start-yarn.sh
wait

##
# start supervisor
##
$HOME/anaconda/bin/supervisord