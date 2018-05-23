## Install spark on ubuntu 14.04

##
# declare vars
##
HOME="/home/vagrant"
VAGRANT_VOL="/vagrant"
## software packages
SPARK_URL=http://d3kbcqa49mib13.cloudfront.net/spark-1.6.2-bin-hadoop2.4.tgz
HADOOP_URL=http://s3.amazonaws.com/spark-related-packages/hadoop-2.4.0.tar.gz
ANACONDA_URL=https://repo.continuum.io/archive/Anaconda2-4.1.1-Linux-x86_64.sh

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
# download packages
##
function download() {
   echo "Downloading $1"
   wget -q $1
}

download $SPARK_URL
download $HADOOP_URL
download $ANACONDA_URL

# prepare for spark installation
if [[ ! -d $HOME/spark ]]; then
    mkdir $HOME/spark
fi
tar -zxf spark-2.0.0-bin-hadoop2.4.tgz --strip 1 -C $HOME/spark
rm -rf $HOME/spark/conf
ln -s /vagrant/provision/conf /home/vagrant/spark/conf

##
# setup hadoop
##
if [[ ! -d $HOME/hadoop ]]; then
    mkdir $HOME/hadoop
fi
tar -zxf hadoop-2.4.0.tar.gz --strip 1 -C $HOME/hadoop
rm -rf /home/vagrant/hadoop/etc/hadoop
ln -s /vagrant/provision/conf /home/vagrant/hadoop/etc/hadoop
ln -s /vagrant/provision/conf /home/vagrant/hadoop/conf
ln -s /home/vagrant/hadoop/bin/* /home/vagrant/hadoop/sbin/.


##
# install conda
##
sudo chmod a+x ./Anaconda2-4*
echo "installing Anaconda2-4.1.1-Linux-x86_64.sh"
./Anaconda2-4.1.1-Linux-x86_64.sh -p $HOME/anaconda -b

##
# set & load necessary env variables
##
cat >> .bashrc << EOF
export PATH=$HOME/anaconda/bin:/home/vagrant/hadoop/bin/:/home/vagrant/spark/bin/:$PATH
export SPARK_HOME=$HOME/spark
export PYTHONPATH=$HOME/anaconda:$HOME/spark/python:$HOME/spark/python/lib/py4j-0.10.1-src.zip
export PYSPARK_PYTHON=$HOME/anaconda/bin/python
export PYSPARK_DRIVER_PYTHON=$HOME/anaconda/bin/python
export HADOOP_HOME="/home/vagrant/hadoop"
export SPARK_MASTER_IP=127.0.0.1
export SPARK_SUBMIT_LIBRARY_PATH="/home/vagrant/hadoop/lib/native/"
export SPARK_SUBMIT_CLASSPATH="/home/vagrant/hadoop/conf/"
export JAVA_HOME="/usr/lib/jvm/java-1.7.0-openjdk-amd64"
export YARN_CONF_DIR="/root/vagrant/hadoop/conf"
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
