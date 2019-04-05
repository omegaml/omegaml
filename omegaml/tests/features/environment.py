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
    # setup omegaml
    import omegaml as om
    use_fixture(splinter_browser, context)
    # set url and admin password
    context.web_url = os.environ.get('OMEGA_URL', 'http://localhost:5000')
    # setup environment
    context.debug = os.environ.get('DEBUG', False)
    defaults = settings()
    context.om = om.setup()


def after_step(context, step):
    context.screenshotfn = os.path.join('/tmp', step.name + '.png')
    context.browser.screenshot(context.screenshotfn)


def after_scenario(context, scenario):
    for omstore in (context.om.datasets, context.om.jobs):
        [omstore.drop(name) for name in omstore.list()]
