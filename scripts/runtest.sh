#!/usr/bin/env bash
export CA_CERTS_PATH=`realpath ./release/dist/omegaml-dev/etc/mongo/certs/ca_certificate.pem`
export MONGO_ADMIN_URL=mongodb://admin:jk3XVEpbpevN4BgtEbmcCpVM24gc7RVB@localhost:27017/admin
export OMEGA_MONGO_URL=mongodb://admin:jk3XVEpbpevN4BgtEbmcCpVM24gc7RVB@localhost:27017/userdb
export OMEGA_BROKER=amqp://omegaml:ZQQycr43FQFe9fqWqh2KBmauAGT9XdUe@localhost:5671/omegaml
export BROKER_URL=amqp://localhost:5671//
export BROKER_HOST=localhost:5671
export OMEGA_USESSL=yes

function install() {
    conda create --offline -q -y -n omenv
    conda activate omenv
    conda install -q -y --file conda-requirements.txt
    pip install -U pip
    pip install --ignore-installed --progress-bar off -r pip-requirements.txt
    pip install --ignore-installed --progress-bar off -r pip-requirements.extra
    pip install --ignore-installed --progress-bar off -r docs/requirements.txt
    pip install -e .[all]
}

function run() {
    docker-compose up -d
    echo "Waiting..."
    sleep 10
    scripts/initlocal.sh
    make test
    docker-compose down
}

install
run
