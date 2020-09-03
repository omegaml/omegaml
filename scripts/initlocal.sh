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

pushd $omegamlee_dir

function installdeps() {
  # install sibling projects
  pushd $projects_dir
  git clone https://github.com/omegaml/omegaml omegaml-ce
  git clone --depth 1 https://7e7710a308996277fc9d448719d078f31193385a@github.com/omegaml/cloudmgr
  git clone --depth 1 https://7e7710a308996277fc9d448719d078f31193385a@github.com/productaize/stackable
  git clone --depth 1 https://7e7710a308996277fc9d448719d078f31193385a@github.com/productaize/landingpage
  git clone --depth 1 https://7e7710a308996277fc9d448719d078f31193385a@github.com/omegaml/ccbackend
  git clone --depth 1 https://7e7710a308996277fc9d448719d078f31193385a@github.com/omegaml/minibatch
  git clone --depth 1 https://7e7710a308996277fc9d448719d078f31193385a@github.com/miraculixx/django-tastypie-swagger
  git clone --depth 1 https://7e7710a308996277fc9d448719d078f31193385a@github.com/miraculixx/tastypiex
  git clone --depth 1 https://7e7710a308996277fc9d448719d078f31193385a@github.com/omegaml/apps
  #pushd omegaml-ce
  #git fetch && git checkout 89bdb9692160a02b8f88851e00b37f1655b4c3ad
  #popd
  popd
}

function activate_conda() {
    source ~/miniconda3/etc/profile.d/conda.sh
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
    curl -O --silent --show-error https://repo.anaconda.com/miniconda/Miniconda3-4.5.12-Linux-x86_64.sh
    sh Miniconda3-4.5.12-Linux-x86_64.sh -b
    cat ~/miniconda3/etc/profile.d/conda.sh >> ~/.bashrc
    activate_conda
    conda install -y --file conda-requirements.txt
}

function install() {
    activate_conda
    pip install --progress-bar off -e $omegamlcore_dir[all]
    pip install --progress-bar off -e $omegamlee_dir[all]
    pip install --progress-bar off -U -r requirements.dev
}

function initlocal() {
    activate_conda
    rm -f db.sqlite3
    rm -f jupyterhub.sqlite
    cat scripts/mongoinit.js | docker-compose exec -T mongodb mongo
    python manage.py migrate
    python manage.py loaddata --app omegaweb landingpage
    python manage.py omsetupuser --username omops --staff --apikey 686ae4620522e790d92009be674e3bdc0391164f --force
    python manage.py omsetupuser --username admin --email admin@omegaml.io --password test --staff --admin --nodeploy
    python manage.py omsetupuser --username jyadmin --staff --apikey b7b034f57d442e605ab91f88a8936149e968e12e
    python manage.py omsetupuser --username demo --apikey bac64ca4cac06325dcaf4643000f58d482f82553
}

# create and install conda env
if [ ! -z $deps ]; then
    installdeps
fi

if [ ! -z $setup ]; then
    setup
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


