Deployment using docker-compose
-------------------------------

Using docker-compose we can deploy a fully functional instance of the platform
locally.

.. code-block:: yaml

        version: '3'
        services:
           nginx:
              image: nginx
              container_name: nginx
              ports:
              - 5000:5000
              - 5671:5671
              - 27017:27017
              - 8899:8888
              - 8010:8010
              links:
                 - rabbitmq
                 - mongodb
                 - omegaml
                 - omjobs
                 - apphub
              volumes:
                 - ./etc/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
                 - ./etc/nginx/http.conf:/etc/nginx/conf.d/http.conf:ro
                 - ./etc/nginx/stream.conf:/etc/nginx/conf.d/stream.conf:ro
           omegaml:
              image: omegaml/omegaml-ee:latest
              container_name: omegaml
              hostname: omegaml
              links:
                 - rabbitmq
                 - mongodb
                 - mysql
              working_dir: /app
              command: scripts/startweb.sh
              volumes:
                 - pythonlib:/app/pylib/user
              environment:
                 - APP=omegaml
                 - APP_CONFIG=EnvSettings_docker
                 - MYSQL_DATABASE=omegaml
                 - MYSQL_USER=omegaml
                 - MYSQL_PASSWORD=mysql
                 - OMEGA_BROKER=amqp://omegaml:changeme@rabbitmq:5671/omegaml
                 - BROKER_URL=amqp://omegaml:changeme@rabbitmq:5671/omegaml
                 - OMEGA_BROKERAPI_URL=http://admin:changeme@rabbitmq:15672/
                 - MONGO_ADMIN_URL=mongodb://admin:changeme@mongodb/admin
                 - OMEGA_MONGO_URL=mongodb://admin:changeme@mongodb/userdb
                 - OMEGA_JYHUB_USER=jyadmin
                 - OMEGA_JYHUB_APIKEY=changeme
                 - JYHUB_HOST=localhost:8899
                 - MONGODB_SERVICE_HOST=mongodb
                 - OMEGA_USESSL=True
                 - CA_CERTS_PATH=/app/etc-dev/mongo/certs/ca_certificate.pem
                 - CELERY_Q=default
                 - PYTHONUSERBASE="/app/pylib/user"
           apphub:
              image: omegaml/apphub:latest
              container_name: apphub
              hostname: apphub
              links:
                 - mongodb
                 - rabbitmq
                 - omegaml
                 - redis
              working_dir: /app
              command: scripts/startapphub.sh
              volumes:
                 - pythonlib:/app/pylib/user
                 - ./etc-dev/mongo/certs/ca_certificate.pem:/app/etc-dev/mongo/certs/ca_certificate.pem
              environment:
                 - OMEGA_BROKER=amqp://omegaml:changeme@rabbitmq:5671/omegaml
                 - OMEGA_RESTAPI_URL=http://omegaml:5000/
                 - CA_CERTS_PATH=/app/etc-dev/mongo/certs/ca_certificate.pem
                 - CELERY_Q=default
                 - APP_CONFIG=EnvSettings_omegacloud_compose
                 - WEB_CONCURRENCY=4
                 - SESSION_TYPE=redis
                 - SESSION_REDIS=redis://:changeme@redis
                 - APPHUB_REGISTRY=apphub.contrib.registry.omegareg.OmegaCloudRegistry
                 - APPHUB_URL_PREFIX=/apps
                 - PYTHONUSERBASE="/app/pylib/user"
           # apphub caching
           redis:
              image: redis
              hostname: redis
              command: redis-server --requirepass changeme
           omjobs:
              image: omegaml/omegaml-ee:latest
              container_name: omjobs
              hostname: omjobs
              links:
                 - omegaml
                 - mongodb
              working_dir: /app
              command: scripts/omegajobs.sh
              volumes:
                 - pythonlib:/app/pylib/user
              environment:
                 - APP=omjobs
                 - OMEGA_RESTAPI_URL=http://omegaml:5000/
                 - OMEGA_BROKER=amqp://omegaml:changeme@rabbitmq:5671/omegaml
                 - MONGO_ADMIN_URL=mongodb://admin:changeme@mongodb/admin
                 - OMEGA_MONGO_URL=mongodb://admin:changeme@mongodb/userdb
                 - OMEGA_JYHUB_USER=jyadmin
                 - OMEGA_JYHUB_APIKEY=changeme
                 - OMEGA_JYHUB_TOKEN=changeme
                 - OMEGA_USESSL=True
                 - CA_CERTS_PATH=/app/etc-dev/mongo/certs/ca_certificate.pem
                 - PYTHONUSERBASE="/app/pylib/user"
           worker:
              image: omegaml/omegaml-ee:latest
              container_name: worker
              hostname: worker
              links:
                 - rabbitmq
                 - mongodb
                 - omegaml
              working_dir: /app
              command: honcho start worker
              volumes:
                 - pythonlib:/app/pylib/user
              environment:
                 - OMEGA_BROKER=amqp://omegaml:changeme@rabbitmq:5671/omegaml
                 - MONGO_ADMIN_URL=mongodb://admin:changeme@mongodb/admin
                 - OMEGA_MONGO_URL=mongodb://admin:changeme@mongodb/userdb
                 - OMEGA_RESTAPI_URL=http://omegaml:5000/
                 - C_FORCE_ROOT=yes
                 - OMEGA_USESSL=True
                 - CA_CERTS_PATH=/app/etc-dev/mongo/certs/ca_certificate.pem
                 - CELERY_Q=default
                 - PYTHONUSERBASE="/app/pylib/user"
           omegaops:
              image: omegaml/omegaml-ee:latest
              container_name: omegaops
              hostname: worker
              links:
                 - rabbitmq
                 - mongodb
                 - omegaml
              working_dir: /app
              command: honcho start scheduler omegaops
              volumes:
                 - pythonlib:/app/pylib/user
              environment:
                 - OMEGA_USERID=omops
                 - OMEGA_APIKEY=changeme
                 - OMEGA_BROKER=amqp://omegaml:changeme@rabbitmq:5671/omegaml
                 - MONGO_ADMIN_URL=mongodb://admin:changeme@mongodb/admin
                 - OMEGA_MONGO_URL=mongodb://admin:changeme@mongodb/userdb
                 - OMEGA_RESTAPI_URL=http://omegaml:5000/
                 - C_FORCE_ROOT=yes
                 - MYSQL_DATABASE=omegaml
                 - MYSQL_USER=omegaml
                 - MYSQL_PASSWORD=mysql
                 - OMEGA_USESSL=True
                 - CA_CERTS_PATH=/app/etc-dev/mongo/certs/ca_certificate.pem
                 - PYTHONUSERBASE="/app/pylib/user"
           rabbitmq:
              image: rabbitmq
              container_name: rabbitmq
              hostname: rabbitmq
              volumes:
                 - ./etc-dev/rabbitmq/definitions.json:/etc/rabbitmq/definitions.json
                 - ./etc-dev/rabbitmq/enabled_plugins:/etc/rabbitmq/enabled_plugins
                 - ./etc-dev/rabbitmq/rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf
                 - ./etc-dev/rabbitmq/certs:/etc/rabbitmq/certs
              ports:
                 - "15672:15672"
           mongodb:
              # initialize by running cat scripts/mongoinit.js | docker exec -i mongodb_1 mongo
              image: mongo:3.6.8-stretch
              container_name: mongodb
              hostname: mongodb
              volumes:
                 - ./etc-dev/mongo/certs/server_key.pem:/etc/mongo/server_key.pem
              command:
                 - "--auth"
                 - "--sslMode"
                 - "preferSSL"
                 - "--sslPEMKeyFile"
                 - "etc/mongo/server_key.pem"
                 - "--oplogSize"
                 - "100"
           mysql:
              image: mysql
              environment:
                 - MYSQL_ROOT_PASSWORD=rootadmin
                 - MYSQL_DATABASE=omegaml
                 - MYSQL_USER=omegaml
                 - MYSQL_PASSWORD=mysql

        volumes:
           pythonlib:
