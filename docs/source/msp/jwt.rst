Authentication using JWT
========================

The default authentication environment accepts both JWT and api keys. This
guide describes

a) how to access the commercial edition's runtime with either a valid
   userid/apikey combination, or a JWT
b) the configuration for a JWT runtime that can only be accessed using
   a JWT token, and does not accept userid/apikeys

Access using JWT instead of apikey
----------------------------------

To retrieve a JWT::

    $ curl -X POST -H "Content-Type: application/json" -d '{"username":"omdemo@omegaml.io","password":"foobar"}' http://hub:8000/token-auth/
    {"token_type": "Bearer", "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjo0LCJlbWFpbCI6Im9tZGVtb0BvbWVnYW1sLmlvIiwidXNlcm5hbWUiOiJvbWRlbW8iLCJleHAiOjE2NTU1NTU4OTd9.2jGQTNBqIZ2Uy
    MKj8uhZBVrW1SGjorcFlyQEJ4Wq49o", "expires_in": 300.0}

For the omegal configuration, login using the JWT :code:`token` value as follows::

    $ om cloud login jwt <token>

Note this will create a config.yml that uses the userid/apikey configuration
for any future login. To permanently use a JWT, change the config.yml file as
follows::

    OMEGA_USERID: "jwt"
    OMEGA_APIKEY: "<token>"


JWT-only Configuration
----------------------

We can enforce that the the omega runtime can only be accessed using a valid
JWT token, effectively disabling userid/apikey access. Provide
the following environment or settings configuration variable::

    OMEGA_AUTH_ENV="omegaee.runtimes.auth.JWTCloudRuntimeAuthenticationEnv"

If the JWT is provided from a different source than omegaml itself, you must
provide appropriate configuration using custom settings::

    JWT_ALGORITHM = 'HS256'
    JWT_ALLOW_REFRESH = False
    JWT_AUDIENCE = None
    JWT_AUTH_HEADER_PREFIX = 'Bearer'
    JWT_EXPIRATION_DELTA = datetime.timedelta(seconds=300)
    JWT_LEEWAY = 0
    JWT_LOGIN_URLS = [settings.LOGIN_URL]
    JWT_REFRESH_EXPIRATION_DELTA = datetime.timedelta(days=7)
    JWT_SECRET_KEY: SECRET_KEY
    JWT_VERIFY = True
    JWT_VERIFY_EXPIRATION = True
