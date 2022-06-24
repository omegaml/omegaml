import datetime

from stackable import StackableSettings


class Config_DjangoJWTAuth:
    # https://github.com/webstack/django-jwt-auth
    _addl_mddlware = (
        'jwt_auth.middleware.JWTAuthenticationMiddleware',
    )
    StackableSettings.patch_list('MIDDLEWARE', _addl_mddlware)
    # get userid from given username
    JWT_PAYLOAD_USERNAME_KEY = 'username'
    JWT_PAYLOAD_GET_USER_ID_HANDLER = 'tastypiex.jwtauth.jwt_get_user_id_from_payload_handler'
    JWT_EXPIRATION_DELTA = datetime.timedelta(300)

