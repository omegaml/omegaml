#!/bin/bash
## package
##
## Initialize a local deployment
##    @script.name [option]
##
## Options:
##      --install      if specified install dependencies
##

# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit
source $script_dir/omutils

omegamlee_dir=$script_dir/..
omegamlcore_dir=$omegamlee_dir/../omegaml-ce

pushd $omegamlee_dir
rm -f db.sqlite3
rm -f jupyterhub.sqlite

if [ ! -z $install ]; then
    pip install -e $omegamlcore_dir[all]
    pip install -e $omegamlee_dir[all]
    pip install -U -r requirements.dev
fi

function initlocal() {
    cat scripts/mongoinit.js | docker-compose exec -T mongodb mongo
    python manage.py migrate
    python manage.py loaddata landingpage.json
    python manage.py omsetupuser --username admin --email admin@omegaml.io --password test --admin --nodeploy
    python manage.py omsetupuser --username jyadmin --staff --apikey b7b034f57d442e605ab91f88a8936149e968e12e
    python manage.py omsetupuser --username omops --staff --apikey 686ae4620522e790d92009be674e3bdc0391164f
    python manage.py omsetupuser --username demo --apikey bac64ca4cac06325dcaf4643000f58d482f82553
}

initlocal
popd
