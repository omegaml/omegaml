# TODO move to landingpage
from datetime import datetime
from functools import lru_cache

import jwt
from cryptography.hazmat.primitives import serialization
from jwt import ExpiredSignatureError
from jwt import PyJWKClient

# jwt authentication adopted from webstack-django-jwt-auth, without django dependency
# see https://pypi.org/project/webstack-django-jwt-auth/
from omegaee.runtimes.auth.apikey import CloudRuntimeAuthenticationEnv
from omegaml import settings  # noqa
from omegaml.client.auth import OmegaRuntimeAuthentication


class AuthenticationFailed(Exception):
    # adopted from jwt_auth.exceptions
    status_code = 401
    detail = "Incorrect authentication credentials."

    def __init__(self, detail=None):
        super().__init__(self)
        self.detail = detail or self.detail

    def __str__(self):
        return self.detail


class JWTOmegaRuntimeAuthentation(OmegaRuntimeAuthentication):
    def __init__(self, userid, token, qualifier='default'):
        self.userid = userid
        self.apikey = token
        self.qualifier = qualifier


class JWTCloudRuntimeAuthenticationEnv(CloudRuntimeAuthenticationEnv):
    # implements JWT auth adopted from jwt_auth, without Django dependency
    from omegaee import eedefaults as settings
    allow_apikey = True

    @classmethod
    def get_runtime_auth(cls, defaults=None, om=None):
        # provide jwt auth for the runtime, allow fallback to api key
        # -- assumes the defaults/om.apikey is a jwt
        # -- if it is not, fallback to apikey
        # -- to force jwt, use userid = 'jwt:<userid>'
        kind = cls.get_restapi_auth(defaults=defaults, om=om).kind
        if kind == 'jwt':
            auth = cls.get_runtime_auth_jwt(defaults=defaults, om=om)
        elif getattr(settings, 'OMEGA_ALLOW_APIKEY', cls.allow_apikey):
            auth = super().get_runtime_auth(defaults=defaults, om=om)
        else:
            raise AuthenticationFailed('Invalid token or apikey')
        return auth

    @classmethod
    def jwt_decode_handler(cls, token, defaults=None):
        defaults = defaults or settings()
        # -- ensure token is a byte string
        token = token.encode('utf8') if isinstance(token, str) else token
        if getattr(defaults, 'JWT_PUBLIC_KEY_URI', None):
            payload = cls.jwt_decode_from_uri(token, defaults=defaults)
        else:
            payload = cls.jwt_decode_handler_single(token, defaults=defaults)
        return payload

    @classmethod
    def jwt_decode_handler_single(cls, token, defaults=None, key=None):
        # adopted from jwtauth.utils to work without Django (we don't have django in a worker)
        settings = defaults or cls.settings
        options = {
            "verify_aud": settings.JWT_AUDIENCE is not None,
            "verify_exp": settings.JWT_VERIFY_EXPIRATION,
            "verify_signature": settings.JWT_VERIFY,
        }
        return jwt.decode(
            jwt=token,
            key=key or settings.JWT_SECRET_KEY,
            algorithms=settings.JWT_ALGORITHM.split(','),
            options=options,
            leeway=settings.JWT_LEEWAY,
            audience=settings.JWT_AUDIENCE,
        )

    @classmethod
    def jwt_decode_from_uri(cls, token, defaults=None):
        # we can have multiple authentication realms, which may have
        # differing signing keys. thus we try to decode with each key in turn
        jwt_uris = defaults.JWT_PUBLIC_KEY_URI.split(',')
        for uri in jwt_uris:
            try:
                key = key_resolver.get_public_key(uri)
                payload = cls.jwt_decode_handler_single(token, defaults=defaults, key=key)
            except ExpiredSignatureError as e:
                # key_resolver caches keys so we must invalidate the cache if the key has expired
                # enforce reloading key on next try
                key_resolver.get_public_key.cache_clear()
            except Exception as e:
                # do not handle exception in hope of another key that matches
                pass
            else:
                break
        else:
            # no key matched, deny access
            raise AuthenticationFailed()
        return payload

    @classmethod
    def jwt_get_user_id_from_payload(cls, payload, defaults=None):
        """
        Override this function if user_id is formatted differently in payload
        """
        # adopted from jwtauth.utils (we don't have django in a worker)
        settings = defaults or cls.settings
        userid = payload.get(getattr(settings, 'JWT_PAYLOAD_USERNAME_KEY', 'preferred_username'))
        return userid

    @classmethod
    def get_runtime_auth_jwt(cls, defaults=None, om=None):
        # expect a jwt token for runtime authentication
        assert defaults or om, "require either defaults or om"
        defaults = defaults or om.defaults
        token = defaults.OMEGA_APIKEY
        payload = cls.get_payload_from_token(token, defaults=defaults)
        userid = cls.jwt_get_user_id_from_payload(payload, defaults=defaults)
        return JWTOmegaRuntimeAuthentation(userid, token,
                                           defaults.OMEGA_QUALIFIER)

    @classmethod
    def get_token_from_request(cls, request):
        # adopted from jwt_auth.mixins
        # convenience method to avoid global dependency on jwt_auth
        from jwt_auth.mixins import get_token_from_request
        return get_token_from_request(request)

    @classmethod
    def get_payload_from_token(cls, token, defaults=None):
        # adopted from jwt_auth.mixins (we don't have django in a worker)
        try:
            payload = cls.jwt_decode_handler(token, defaults=defaults)
        except jwt.ExpiredSignatureError as e:
            raise AuthenticationFailed(f"Signature has expired, {e}")
        except jwt.DecodeError as e:
            raise AuthenticationFailed(f"Error decoding token due to {e}.")

        return payload


def _create_jwt_token(defaults=None, om=None):
    # use for testing only
    from django.conf import settings
    from jwt_auth import settings as jwt_auth_settings

    defaults = defaults or om.defaults
    payload = {
        "username": defaults.OMEGA_USERID,
        "exp": datetime.utcnow() + settings.JWT_EXPIRATION_DELTA,
    }
    token = jwt_auth_settings.JWT_ENCODE_HANDLER(payload)
    return token


# TODO refactor into common library
class PublicKeyResolver(PyJWKClient):
    # get JWT signing key from KEYCLOAK_CERT_URI
    # adopted from https://github.com/jpadilla/pyjwt/issues/722#issuecomment-1017941663
    @lru_cache(maxsize=1)
    def _default_algorithms(self):
        from jwt.algorithms import get_default_algorithms
        return get_default_algorithms()

    @lru_cache
    def get_public_key(self, uri):
        self.uri = uri
        keys = self.get_signing_keys()
        # https://cryptography.io/en/latest/hazmat/primitives/asymmetric/rsa/
        jwtkey = keys[0]
        pem = jwtkey.key.public_bytes(encoding=serialization.Encoding.PEM,
                                      format=serialization.PublicFormat.SubjectPublicKeyInfo)
        return pem

    def fetch_data(self):
        data = super().fetch_data()
        return {"keys": [key for key in data.get("keys", []) if key.get("alg", None) in self._default_algorithms()]}


key_resolver = PublicKeyResolver('notset', cache_keys=True)
