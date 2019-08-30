#!/usr/bin/env bash
omegamlcore_dir=../omegaml-ce
omegamlcore_scripts_dir=$omegamlcore_dir/scripts
docker-compose -f $omegamlcore_dir/docker-compose-dev.yml up -d
cat $omegamlcore_scripts_dir/mongoinit.js | docker exec -i omegaml-ce_mongo_1 mongo
export DJANGO_DEBUG=1
python manage.py migrate
PORT=8000 honcho start web worker notebook
