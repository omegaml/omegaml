# -- FILE: features/environment.py
# CONTAINS: Browser fixture setup and teardown
import os
from behave import fixture, use_fixture
from splinter.browser import Browser

from omegaml import settings


@fixture
def splinter_browser(context):
    context.browser = Browser('chrome')
    yield context.browser
    context.browser.quit()


def before_all(context):
    use_fixture(splinter_browser, context)
    context.web_url = os.environ.get('OMEGA_URL', 'https://omegaml.omegaml.io')
    context.debug = os.environ.get('DEBUG', False)
    defaults = settings()
    defaults.OMEGA_AUTH_ENV = 'omegacommon.auth.OmegaSecureAuthenticationEnv'
