#!/bin/bash
#chmod 755 $rabbitmq_certs_dir/server_certificate.pem $rabbitmq_certs_dir/server_key.pem $rabbitmq_certs_dir/ca_certificate.pem
# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
#source $script_dir/easyoptions || exit

mongo_certs_dir=$script_dir/../release/dist/omegaml-dev/etc/mongo/certs/
rabbitmq_certs_dir=$script_dir/../release/dist/omegaml-dev/etc/rabbitmq/certs/

# Remove old certificates and recreate SSL directories
rm -rf $mongo_certs_dir
rm -rf $rabbitmq_certs_dir

mkdir -p $mongo_certs_dir
mkdir -p $rabbitmq_certs_dir

# Clone tls-gen in upper directory
cd $script_dir/../..
#git clone https://github.com/michaelklishin/tls-gen.git
cd tls-gen/basic

# Create and move rabbitmq certs, use container hostname as CN
make PASSWORD=pass CN=rabbitmq
# Move certs to appropriate place in the repo
mv result/server_key.pem result/server_certificate.pem result/ca_certificate.pem $rabbitmq_certs_dir
rm -rf result
# Rabbitmq user in that container does not have permission for files
# Do this only for development certificates
chmod 755 $rabbitmq_certs_dir/server_certificate.pem $rabbitmq_certs_dir/server_key.pem $rabbitmq_certs_dir/ca_certificate.pem

# Create and move mongodb certs, use container hostname as CN
make PASSWORD=pass CN=mongodb
# Mongo expects key and certificate in a single file
cat result/server_certificate.pem >> result/server_key.pem
# Move certs to appropriate place in the repo
mv result/server_key.pem result/server_certificate.pem result/ca_certificate.pem $mongo_certs_dir
rm -rf result
# Do this only for development certificates
chmod 755 $mongo_certs_dir/server_certificate.pem $mongo_certs_dir/server_key.pem $mongo_certs_dir/ca_certificate.pem
