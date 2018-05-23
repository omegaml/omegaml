export JAVA_HOME="/usr/lib/jvm/java-1.7.0-openjdk-amd64"
export HADOOP_HOME="/home/vagrant/hadoop"
export HADOOP_HEAPSIZE=1000
export HADOOP_OPTS="-Djava.net.preferIPv4Stack=true"
export HADOOP_NAMENODE_OPTS="-Dcom.sun.management.jmxremote $HADOOP_NAMENODE_OPTS"
export HADOOP_SECONDARYNAMENODE_OPTS="-Dcom.sun.management.jmxremote $HADOOP_SECONDARYNAMENODE_OPTS"
export HADOOP_DATANODE_OPTS="-Dcom.sun.management.jmxremote $HADOOP_DATANODE_OPTS"
export HADOOP_BALANCER_OPTS="-Dcom.sun.management.jmxremote $HADOOP_BALANCER_OPTS"
export HADOOP_JOBTRACKER_OPTS="-Dcom.sun.management.jmxremote $HADOOP_JOBTRACKER_OPTS"
export HADOOP_SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=5"
export HADOOP_LOG_DIR=/home/vagrant/ephemeral-hdfs/logs
export HADOOP_NAMENODE_USER=vagrant
export HADOOP_DATANODE_USER=vagrant
export HADOOP_SECONDARYNAMENODE_USER=vagrant
export HADOOP_JOBTRACKER_USER=vagrant
export HADOOP_TASKTRACKER_USER=vagrant
