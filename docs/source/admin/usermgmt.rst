User Management
===============

Concepts
--------

* *User Account* - an entity known to the platform by a userid. A user account
  is protected by a password to log in through the webui, and is associated
  with an apikey, or a token issued by a third-party IDP, to access REST API services.

* *User Group* - a collection of User Accounts into groups, to ease administrative
  tasks in assigning permissions. A User Group needs to be associated with a
  like-named User Group Account, so that omegaml can associate services with the
  User Group.

* *User Group Account* - like a User Account, however User Group Accounts are
  solely used for service administration. User Group Accounts cannot be used
  to sign in and are considered non-permissioned on the platform. Their sole
  purpose is to serve user configurations for User Accounts assigned to a
  User Group.

* *User Roles* - assigns default permissions with respect to the webui objects.
  There are three roles: Admin, Staff, User. Admin users have all rights over
  all objects. Staff users are like admin, but with specifically permissioned
  rights. Users who have neither admin nor staff roles enabled can only access
  their own objects.

* *Apikeys* - every user has an assigned apikey. Apikeys are the primary
  token that clients can use to access REST API services. For all intent and
  purpose, an apikey should be considered a static access token and be guarded
  like a password.

* *IDP Account* - when configured, users can login to the platform by a third-
  party authorization service known as an Identity Provider (IDP). When this
  is enabled, REST APIs can be access through JWT, a popular form of access
  tokens issued by an IDP. JWTs are similar to apikeys, however they have
  restricted validity, can carry additional information related to the user,
  and can be cryptographically signed.

* *Service Deployment* - every User Account, including Group User Accounts,
  can have one or more Service Deployments assigned, including custom defined
  services. Examples include the omegaml deployment at a per-user level,
  dynamically deployed workers, or application services deployed on behalf of
  a user. The `omegaml` Service Deployment manages the session configuration
  that is accessed and used by

  .. note::

    User Roles do _not_ govern objects stored and processed by omegaml clients
    and workers. These objects are protected by the analytics database used
    by omega-ml, in particular MongoDB. However, Admin and Staff users can
    access Deployment Services, as well as api keys, and could thus gain
    access to any of the objects in MongoDB by using these credentials. It
    is possible to define a User Group for Staff users, and permission these
    users for specific, restricted access such that they have no visibility
    into Deployment Services.


User sign-up and omega-ml service deployment
--------------------------------------------

.. _`password strength`: https://en.wikipedia.org/wiki/Password_strength

Users can sign-up to the webui at https://omegaml.yourdomain.com. For every
new user-sign up the "signup" Service Command is issued. By default, this
will trigger the "omegaml" deployment for the user as follows:

1. Create the 'omegaml' Service Deployment assigned to the user
2. Create a new MongoDB for this user (dbname + password are 36-byte randomized each)
3. Create a MongoDB user read/write permissioned to the new mongodb

The user is provided with the default RabbitMQ credentials, defined by the
platform constants, and shared by all other users without specific RabbitMQ
credentials.


Manual user creation
--------------------

Users be created manually by admin users.

1. login to https://omegaml.yourdomain.com/admin
2. Select *Authentication and Authorization > Users*
3. Click *Add user*
4. Enter a valid email address
5. Enter an initial password (user will have to change on next login)
5. Save

Once the new user is saved, same process as for a self-serviced User sign-up
applies.

Manual service deployment
-------------------------

The omegaml Service Deployment can be recreated or deployed on request for
specific users. This is useful in case of database migrations or when you
need to create dedicated RabbitMQ credentials for a group users.

1. login to https://omegaml.yourdomain.com/admin
2. Select *Service Deployment > Service deploy commands*
3. Click *Add service deploy command*
4. Select the service (Offering) and the User for which to deploy the service
5. Enter `install`  as the phase
6. Enter `vhost=yes` as the Command parameters
7. Save

The `vhost=yes` parameter triggers the deployment of a new RabbitMQ vhost for
this user as follows:

1. A name for the vhost is generated (randomized 36-bytes)
2. The username and password are the same as for the user's mongodb
3. The vhost is deployed
4. vhost, username and password are saved to the user's omegaml
   Service Deployment


User Groups and User Group Accounts
-----------------------------------

User Groups simplify the process of service deployment and enable
re-use of the same session configuration (MongoDB and RabbitMQ)
for multiple users. This facilitates collaboration and enables
organizations to leverage a single MLOps infrastructure for multiple teams.

Create a new User Group
+++++++++++++++++++++++

Create a new User Group as follows:

1. login to https://omegaml.yourdomain.com/admin
2. Select "Authentication and Authorization > Groups"
3. Click "Add Group"
4. Enter a name for the group. Note that only alphanumeric characters
   are allowed and any punctuation will be removed.
5. Select permissions if users of this group should be staff members.
6. Save

User Groups do not have assigned services. To assign a Service Deployment,
add a new User Group Account (see Manual user creation):

1. Select *Authentication and Authorization > Users*
2. Click *Add user*
3. Enter a username of the form `G<group name>`.  The leading *G* is important.
4. Enter an initial password
3. Save

Edit the new user:

1. Select *Authentication and Authorization > Users*
2. Select the new `G<group name>` user
3. Assign the user to the previously created User Group named `<group name>`
4. Save

Add user accounts to a User Group
+++++++++++++++++++++++++++++++++

1. Select *Authentication and Authorization > Users*
2. Open the user you want to assign to this group
3. Assign the user to the `<group name>`

This user can now select a qualifier on omega-ml login that select's the group's
session configuration:

.. code:: bash

    $ om cloud login USERNAME APIKEY <group name>:default




