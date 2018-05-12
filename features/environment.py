# -- FILE: features/environment.py
# CONTAINS: Browser fixture setup and teardown
import os

import yaml
from behave import fixture, use_fixture
from splinter.browser import Browser


@fixture
def splinter_browser(context):
    context.browser = Browser('chrome')
    yield context.browser
    context.browser.quit()


def before_all(context):
    use_fixture(splinter_browser, context)
    secrets = os.path.join(os.path.expanduser('~/.omegaml/behave.yml'))
    with open(secrets) as fin:
        secrets = yaml.load(fin)
    omega_url = os.environ.get('OMEGA_URL', 'https://omegaml.omegaml.io')
    context.secrets = secrets.get(omega_url, secrets)
