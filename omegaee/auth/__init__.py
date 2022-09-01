"""
omega commercial edition authentication
=======================================
licensed use only (c)

omega-ml provides a general IDP authentication framework, and acts as its
own IDP in a minimal configuration. This can be customized to match an
organization's requirement.

The technical implementation leverages existing, well-established frameworks.
It is noteworthy that omegaml does not itself implement any of the
authentication handling by itself, it merely provides customization and
plugins where/as needed.

Use Cases
---------

1. Login to hub (web app)

    1.1 User opens web app in browser
    1.2 Web app checks for existing session. If yes, continue 1.8
    1.3 Redirect user to IDP, e.g. Keycloak (unless existing session detected)
    1.4 IDP responds with authentication code
    1.5 Web app exchanges authentication code for access token
        by calling IDP as an authorized client (client id / client secret)
    1.6 In case of failure to get a valid access token, deny user access
    1.7 User claims (in JWT) are mapped to user groups/permissions (in Django)
    1.8 User is authenticated, session is created (identified in session cookie)

2. Access to REST API (as API client)

    1.1 REST API call provides Authorization header
    1.2 Web app (endpoint) checks authorization token is valid
        - existing Django Session
        - valid userid/apikey
        - valid JWT
    1.3 In case of failure to verify token, deny user access
    1.4 User claims (in JWT) are mapped to user groups/permissions (in Django)
    1.5 User is authenticated, request is forwarded to view/request handler

3. Runtime execution of task

    1. in client
    1.1 User starts with authenticated Omega instance (authenticated session)
    1.2 User submits task to a runtime worker (om.runtime.task(...).apply_async)
    1.3 omegaml.OmegaRuntime submits authentication token along task request

    2. in worker
    2.1 omegaml.OmegaTask receives token and provides to its AuthenticationEnv.secure()
    2.2 secure AuthenticationEnv forwards token to hub, receiving session configuration
    2.3 AuthenticationEnv provides Omega() instance using session configuration
    2.4 task execution starts
    2.5 worker clears Authentication (unless cached sessions are enabled)


Technical implementation
------------------------

1. Web app

    Implemented using Django AllAuth, Keycloak Provider [1]
    Executes the OAuth2 protocol flow according to [2]
    Defined in settings.SOCIALACCOUNT_PROVIDERS [3]
    Customization via SOCIALACCOUNT_ADAPTER or socialaccount signal [3]

    [1] https://django-allauth.readthedocs.io/en/latest/providers.html#keycloak
    [2] https://auth0.com/docs/get-started/authentication-and-authorization-flow/authorization-code-flow
    [3] config.env_sgbk.EnvSettings_SGKB_Kubernetes


2. REST API

    Implemented using tastypie Authentication mechanism [1]
    Adopted for JWT authentication using Django JWT auth [2]
    Actual Authentication class is omegaee.auth.OmegaJWTAuthentication [3]
    OmegaJWTAuthentication uses the OMEGA_AUTHENV configured by settings [4]
    The JWT token is decoded by settings.JWT_DECODE_HANDLER
    User is retrieved from settings.JWT_PAYLOAD_GET_USER_ID_HANDLER [5]

    [1] https://django-tastypie.readthedocs.io/en/latest/authentication.html
    [2] https://github.com/webstack/django-jwt-auth
    [3] https://github.com/productaize/tastypiex/blob/master/tastypiex/jwtauth.py
    [4] https://github.com/webstack/django-jwt-auth#additional-settings
    [5] config.env_sgbk.EnvSettings_SGKB_Kubernetes

3. Runtime

    Implemented using omegaml.AuthenticationEnv [1]
    Actual class is omegaee.JWTCloudRuntimeAuthenticationEnv [1]
    Adopted for JWT authentication using Django JWT auth [2]
    omegaee.JWTCloudRuntimeAuthenticationEnv uses jwt_auth.mixins configured by settings [3]
    Mixins are the same as, and configured as for the REST API
    Note that the runtime will verify the token AND make a request to the hub's config api
      to retrieve the session, the API will verify the token also

    [1] Vendor technical reference
    [2] https://github.com/webstack/django-jwt-auth
    [3] https://github.com/webstack/django-jwt-auth#additional-settings


Customization
-------------

The following constructs can implement custom processing in all of the above use cases.

Web login
+++++++++

This handles the IDP authentication flow and signs the user in for interactive
web sessions. It does _not_ provide the REST API authentication since the latter
already must have the Authorization header including a valid JWT.

1. settings.SOCIALACCOUNT_ADAPTER='myapp.auth.IDPAccountAdapter'

    class IDPAccountAdapter(DefaultSocialAccountAdapter):
        ...
        def pre_social_login(self, request, sociallogin):
            # request is the Django Request instance
            # sociallogin is the allauth.SocialLogin object
            # -- sociallogin.token contains the access token as provided by IDP
            ...

2. handler for social login

    @receiver(pre_social_login)
    def handle_social_login(sender, request, sociallogin, **kwargs):
        ...

    https://django-allauth.readthedocs.io/en/latest/signals.html?highlight=pre_social_login#allauth-socialaccount


REST API
++++++++

The REST API is an http entrypoint and generally requires a client to
pass the Authorization header. The following default implementations are
provided on every endpoint:

    ApiKeyAuthentication -  validates against userid/api key
    OmegaJWTAuthentication -  validates against jwt tokens
    SessionAuthentication - validates against existing sessions (cookie based)

In addition, a custom authentication class may be provided, which will be
called first, if provided.

1. settings.OMEGA_RESTAPI_AUTHENTICATION='myapp.auth.IDPAuthentication'

    class IDPAuthentication(Authentication):
        def is_authenticated(self, request, **kwargs):
            # set request.user and return True if authenticated
            # else return False, or raise tastypie.Unauthorized()

2. settings.JWT_DECODE_HANDLER='myapp.auth.jwt_decode_handler'

    This is used by the OmegaJWTAuthentication class

    def jwt_decode_handler(token):
        decoded = ...
        return decoded

3. settings.JWT_PAYLOAD_GET_USER_ID_HANDLER='myapp.auth.jwt_get_user_id_handler'

    This is used by the OmegaJWTAuthentication class

    def jwt_get_user_id_handler(payload):
        ...
        return user_id


omegaml worker and other clients
--------------------------------

Below applies to both workers and clients (technically a worker is a client).
The specific implementation for workers and clients may vary, e.g. the client
may have different means to retrieve a session configuration than does the worker.

For example, the worker may have cached sessions that it pre-loads or refreshes
independent of requests, and only validate the token, while the client may be
required to always request a new token through a web login.

1. settings.OMEGA_AUTH_ENV='myapp.auth.IDPAuthenticationEnv'

    class IDPAuthenticationEnv(AuthenticationEnv):
        is_secure = True

        def get_omega_from_apikey(self, userid, apikey, **kwargs):
            ...
            return Omega(...)

        def get_omega_from_task(self, task, auth=None):
            ...
            return Omega(...)

        def get_runtime_auth(self, defaults, om=None):
            ...
            return OmegaRuntimeAuthentication(...)


2. subclassing OmegaRuntimeAuthentication

    In your IDPAuthentication.get_runtime_auth() you may instantiate a
    custom runtime authentication as follows:

    class IDPRuntimeAuthentication(OmegaRuntimeAuthentication):
        def __init__(self, *credentials, qualifier=None):
            ...

        @property
        def token(self):
            ...
            return (userid, token, qualifier)


    The .token value is passed as the authentication token to the runtime.
    It is passed to the worker's AuthenticationEnv.get_omega_from_task(task, auth=<token>).
    It is the responsibility of this method to validate the authentication and
    create a properly authenticated Omega() session, including its corresponding
    OmegaRuntimeAuthentication() instance.
"""
