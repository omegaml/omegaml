User Administration
===================

In regards to user accounts the following functionality is available from
the admin UI, the command line as well as from the REST API (partially):

* user registration & sign up
* user profile (username, email, address, activation status)
* outbound email tracking
* service profile (configuration used by omega|ml through its services)

User registration
-----------------

User registration means that a new user account is created from either of
three places:

* web UI: a user signs up interactively using a web browser. an email
  will be sent out, asking the user to confirm the new account by opening
  an auto-generated link

* command line: an admin creates a user account. For all intent and purpose
  this is functionally equivalent to the interactive user sign up via the
  web ui. However admins have more control, e.g. to set up passwords

* REST API: any user with access to the API can create a new user. Again,
  this is functionally equivalent to the web ui. However in this case the
  user receives an email with a confirmation token (instead of a link) which
  has to be provided back to the API as a confirmation of the user creation.
  Admin users (i.e. authorized API clients) can request the token
  programmatically and do not have to rely on email.


User profile
------------

The user profile can be queried from the REST API by admin users. Also the
user profile can be managed from the admin UI.


Service profile
---------------

aka client settings, or just settings

A user's service profile specifies omega|ml resources such as the REST API URL,
jupyter hub URL, storage and runtime endpoints. The profile is used by all
parts of omega|ml to provide user-specific configuration.

The REST API allows users to query but not change the settings. Admin users can
also change the profile via the API.

