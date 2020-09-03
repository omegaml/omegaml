#!/usr/bin/env bash
export CA_CERTS_PATH=`realpath ./release/dist/omegaml-dev/etc/mongo/certs/ca_certificate.pem`
export MONGO_ADMIN_URL=mongodb://admin:jk3XVEpbpevN4BgtEbmcCpVM24gc7RVB@localhost:27017/admin
export OMEGA_MONGO_URL=mongodb://admin:jk3XVEpbpevN4BgtEbmcCpVM24gc7RVB@localhost:27017/userdb
export OMEGA_BROKER=amqp://omegaml:ZQQycr43FQFe9fqWqh2KBmauAGT9XdUe@localhost:5671/omegaml
export OMEGA_BROKERAPI_URL=http://admin:een53uGa8Lvc9mKsyMyXtzH5pAMfD3FP@localhost:15672/
export BROKER_URL=amqp://localhost:5671//
export BROKER_HOST=localhost:5671
export OMEGA_USESSL=yes

function run() {
    docker-compose up mongodb rabbitmq -d
    echo "Waiting..."
    sleep 10
    scripts/initlocal.sh
    make test
    docker-compose down
}

install
run
