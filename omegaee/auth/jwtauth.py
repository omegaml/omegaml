from django.conf import settings
from django.contrib.auth import get_user_model
from omegaml import load_class
from tastypie.authentication import Authentication
from tastypie.compat import get_username_field
from tastypie.http import HttpUnauthorized


# TODO: consolidate with tastypiex, landingpage JWT authentication

class OmegaJWTAuthentication(Authentication):
    """ Handles JWT auth for Tastypie, in which a user provides a valid JWT token

    Uses the omegaml

    Usage::

        class SomeResource(Resource):
                class Meta:
                    authentication = JWTAuthentication()

    See Also
        - backend https://github.com/webstack/django-jwt-auth
    """
    auth_type = 'bearer'
    auth_env = load_class(getattr(settings,
                                  "JWT_AUTH_ENV",
                                  "omegaee.runtimes.auth.JWTCloudRuntimeAuthenticationEnv"))

    def _unauthorized(self):
        return HttpUnauthorized()

    def extract_credentials(self, request):
        auth_env = self.auth_env
        token = auth_env.get_token_from_request(request)
        payload = auth_env.get_payload_from_token(token)
        userid = auth_env.jwt_get_user_id_from_payload(payload)
        return userid, token

    def is_authenticated(self, request, **kwargs):
        """
        Finds the user and checks their API key.

        Should return either ``True`` if allowed, ``False`` if not or an
        ``HttpResponse`` if you need something custom.
        """
        # validate credentials in jwt
        try:
            userid, token = self.extract_credentials(request)
            user = self._get_user(userid)
        except Exception as e:
            return self._unauthorized()
        request.user = user
        return True

    def _get_user(self, userid):
        username_field = get_username_field()
        lookup_kwargs = {username_field: userid}
        UserModel = get_user_model()
        user = UserModel.objects.get(**lookup_kwargs)
        return user
