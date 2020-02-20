#!/usr/bin/env bash
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)

export OMEGA_PORT=5000
export JUPYTER_PORT=8888
export JUPYTER_PARAM="--config ./omegaml/notebook/jupyter/jupyter_notebook_config.py --debug"
export JUPYTER_PASSWORD=sha1:24fa20fec60f:c7cd7e46afa507d484c59abeadbefa05022583b8
export OMEGA_FRAMEWORKS=scikit-learn,keras,tensorflow
export OMEGA_MONGO_URL=mongodb://admin:foobar@localhost/omega
docker-compose -f docker-compose-dev.yml down
docker-compose -f docker-compose-dev.yml up -d --remove-orphans --force-recreate
sleep 5
cat $script_dir/mongoinit.js | docker exec -i omegaml-ce_mongo_1 mongo
honcho start restapi worker notebook
