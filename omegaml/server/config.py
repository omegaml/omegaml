import os


class FlaskConfig:
    basedir = os.path.abspath(os.path.dirname(__file__))
    ASSETS_ROOT = os.getenv('ASSETS_ROOT', '/static/assets')
    SECRET_KEY = os.getenv('SECRET_KEY', '38012cfe0d364bf4e3acffe550e91892c3c50e8160b9e55b50dcdf7d39653b48')
    SESSION_TYPE = "filesystem"


class LiveConfig(FlaskConfig):
    DEBUG = False
    # Security
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 3600


class DevConfig(FlaskConfig):
    DEBUG = True


CONFIG_MAP = {
    'live': LiveConfig,
    'dev': DevConfig,
}
