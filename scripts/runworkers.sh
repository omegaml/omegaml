#!/bin/bash
base_env=$(conda env list | grep base | xargs | cut -d ' ' -f 2)
envs=$(ls -d1 $base_env/envs/* | xargs -L1 basename)
envs="base $envs"
for env in $envs; do
    echo "Activating $env"
    source activate $env
    echo "Starting workers"
    celery -A tasks worker --loglevel=info &
done




