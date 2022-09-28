import datetime
import os


class Config_OmegaJWTAuth:
    # this configures omegaee JWTAuth implementation
    # adopted from https://github.com/webstack/django-jwt-auth
    JWT_AUTH_ENV = 'omegaee.runtimes.auth.JWTCloudRuntimeAuthenticationEnv'
    # https://www.iana.org/assignments/jwt/jwt.xhtml
    JWT_PAYLOAD_USERNAME_KEY = 'preferred_username'
    JWT_EXPIRATION_DELTA = datetime.timedelta(300)
    JWT_ALGORITHM = "HS256"
    JWT_SECRET_KEY = ""
    JWT_PUBLIC_KEY_URI = os.environ.get('KEYCLOAK_CERT_URI', None)
    JWT_VERIFY = False
    JWT_LEEWAY = 0
    JWT_AUDIENCE = None
    JWT_VERIFY_EXPIRATION = True
    JWT_WARN_INSECURE = True


