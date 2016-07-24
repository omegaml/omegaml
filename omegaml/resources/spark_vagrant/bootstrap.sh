## Install spark on ubuntu 14.04

##
# declare vars
##
HOME="/home/vagrant"
VAGRANT_VOL="/vagrant"

##
# update apt-cache and install files
##
APT_PACKAGES=""
for PACKAGE in `cat $VAGRANT_VOL/provision/apt-packages`; do
    APT_PACKAGES="$APT_PACKAGES $PACKAGE"
done

##
# Comment out below and replace np.archive.ubuntu to use your local cache repo if any
##
#sudo sed -i 's/archive.ubuntu/np.archive.ubuntu/' /etc/apt/sources.list
sudo apt-get update
sudo apt-get install -y $APT_PACKAGES

##
# download and setup spark
##
echo "Downloading spark-1.6.2-bin-hadoop2.6.tgz"
wget -q http://d3kbcqa49mib13.cloudfront.net/spark-1.6.2-bin-hadoop2.6.tgz
# prepare for spark installation
if [[ ! -d $HOME/spark ]]; then
    mkdir $HOME/spark
fi
tar -zxf spark-1.6.2-bin-hadoop2.6.tgz --strip 1 -C $HOME/spark

##
# download & install conda
##
echo "Downloading Anaconda2-4.1.1-Linux-x86_64.sh"
wget -q https://repo.continuum.io/archive/Anaconda2-4.1.1-Linux-x86_64.sh
sudo chmod a+x ./Anaconda2-4*
echo "installing Anaconda2-4.1.1-Linux-x86_64.sh"
./Anaconda2-4.1.1-Linux-x86_64.sh -p $HOME/anaconda -b

##
# set & load necessary env variables
##
cat >> .bashrc << EOF
export PATH=$HOME/anaconda/bin:$PATH
export SPARK_HOME=$HOME/spark
export PYTHONPATH=$HOME/anaconda:$HOME/spark/python:$HOME/spark/python/lib/py4j-0.9-src.zip
export PYSPARK_PYTHON=$HOME/anaconda/bin/python
export PYSPARK_DRIVER_PYTHON=$HOME/anaconda/bin/python
EOF

##
# ipython setup
##
$HOME/anaconda/bin/ipython profile create pyspark

##
# use local ssh key as authorized keys to start slaves
##
ssh-keygen -f $HOME/.ssh/id_rsa -t rsa -q -P ""
cat $HOME/.ssh/id_rsa.pub >> $HOME/.ssh/authorized_keys