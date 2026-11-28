Install and Deploy MongoDB and RabbitMQ
===============================

Instructions for installing required packages are below

MongoDB
-------

Instructions on how to install MongoDB are available as below:

-  `Ubuntu (asumes Ubuntu
   14.04) <https://www.howtoforge.com/tutorial/install-mongodb-on-ubuntu-14.04/>`__
-  `OSX <https://docs.mongodb.com/manual/tutorial/install-mongodb-on-os-x/>`__

RabbitMQ
--------

Instructions on how to install RabbitMQ are available as below:

-  `Ubuntu <https://www.rabbitmq.com/install-debian.html>`__
-  `OSX <https://www.rabbitmq.com/install-homebrew.html>`__

Post Installation
-----------------

After the application packages are installed, make sure both mongodb and
rabbitmq are setup to listen on all interfaces (or atleast the ones you
are using), you may do so following the instructions as listed below:

-  For mongodb you'd have to edit ``/etc/mongod.conf``, `instructions
   here <http://stackoverflow.com/a/30885474>`__

-  For Rabbitmq, your ``/etc/rabbitmq.config`` may look similar to below

   ::

       # /etc/rabbitmq.config
       # see https://www.rabbitmq.com/networking.html
       #     https://www.rabbitmq.com/access-control.html
       [{rabbit, [{loopback_users, []}]}].
