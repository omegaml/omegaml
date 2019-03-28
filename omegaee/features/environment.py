# -- FILE: features/environment.py
# CONTAINS: Browser fixture setup and teardown
import os
from behave import fixture, use_fixture
from splinter.browser import Browser

from omegaee.features.util import get_admin_secrets
from omegaml import settings


@fixture
def splinter_browser(context):
    context.browser = Browser('chrome')
    yield context.browser
    context.browser.quit()



def before_all(context):
    # get browser
    use_fixture(splinter_browser, context)
    # set url and admin password
    context.web_url = os.environ.get('OMEGA_URL', 'https://omegaml.omegaml.io')
    admin_user, admin_password = get_admin_secrets(context.web_url)
    context.admin_user = os.environ.get('OMEGA_ADMIN_USER', admin_user)
    context.admin_password = os.environ.get('OMEGA_ADMIN_PASSWORD', admin_password)
    # setup environment
    context.debug = os.environ.get('DEBUG', False)
    defaults = settings()
    defaults.OMEGA_AUTH_ENV = 'omegacommon.auth.OmegaSecureAuthenticationEnv'
    context.browser.visit(context.web_url)

