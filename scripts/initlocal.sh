#!/bin/bash
## package
##
## Initialize a local deployment
##    @script.name [option]
##
## Options:
##      --install      if specified install dependencies
##      --setup        if specified create conda env
##      --deps         get sibling repositories
##      --noinit       do not initialize, just setup, deps, install as specified
##

# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit
source $script_dir/omutils

projects_dir=$script_dir/../..
omegamlee_dir=$script_dir/..
omegamlcore_dir=$omegamlee_dir/../omegaml-ce
# set dbms postgres|mysql|mssql (see extras in omegaml/setup.py)
dbms=postgres

function installdeps() {
  # install sibling projects
  pip install gil
  gil clone
}

function activate_conda() {
    source ~/miniforge3/etc/profile.d/conda.sh
    cur_env=`conda info | grep "active environment" | cut -d ":" -f 2 | xargs`
    if [ $cur_env == "None" ]; then
       echo "conda setting up base env"
       cur_env=base
       echo "conda activate base" >> ~/.bashrc
    fi
    echo "activating conda env $cur_env"
    conda activate $cur_env
}

function setup() {
    curl -L -O --silent --show-error "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh"
    bash Miniforge3-Linux-x86_64.sh -b
    cat ~/miniforge3/etc/profile.d/conda.sh >> ~/.bashrc
    activate_conda
}

function install() {
    activate_conda
    conda install -y --file conda-requirements.txt
    pip install --progress-bar off -U -r requirements.dev
    pip install --progress-bar off -U -e ../landingpage[$dbms]
    pip install --progress-bar off -e $omegamlee_dir[all,dev]
}

function initlocal() {
    activate_conda
    rm -f db.sqlite3
    rm -f jupyterhub.sqlite
    cat scripts/mongoinit.js | docker-compose exec -T mongodb mongo
    # make sure the site user directory exists, expected in jupyter spawner
    mkdir -p /app/pylib/user
    # initialize django
    python manage.py migrate
    python manage.py loaddata --app omegaweb landingpage
    python manage.py omsetupuser --username admin --email admin@omegaml.io --password test --staff --admin --nodeploy
    python manage.py omsetupuser --username omops --staff --apikey 686ae4620522e790d92009be674e3bdc0391164f --force
    python manage.py omsetupuser --username jyadmin --staff --apikey b7b034f57d442e605ab91f88a8936149e968e12e
    python manage.py omsetupuser --username omdemo --apikey bac64ca4cac06325dcaf4643000f58d482f82553
}

pushd $omegamlee_dir

if [ ! -z $setup ]; then
    setup
fi

if [ ! -z $deps ]; then
    installdeps
fi

if [ ! -z $install ]; then
    install
fi

if [ -z $noinit ]; then
    initlocal
else
    activate_conda
fi

popd


