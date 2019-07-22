# -- FILE: features/environment.py
# CONTAINS: Browser fixture setup and teardown
import os

from behave import fixture, use_fixture
from splinter.browser import Browser
from selenium.webdriver import ChromeOptions

from omegaml import settings
from omegaml.tests.features.util import istrue


@fixture
def splinter_browser(context):
    headless = istrue(os.environ.get('CHROME_HEADLESS'))
    screenshot_path = os.environ.get('CHROME_SCREENSHOTS', '/tmp')
    options = None
    if headless:
        print("Running headless")
        options = ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--remote-debugging-port=9222')
        options.add_argument('--disable-dev-shm-usage')
    context.browser = Browser('chrome', options=options)
    context.browser.driver.set_window_size(1024, 768)
    context.screenshot_path = screenshot_path
    yield context.browser
    context.browser.quit()


def before_all(context):
    # setup omegaml
    import omegaml as om
    use_fixture(splinter_browser, context)
    # set url and admin password
    context.web_url = os.environ.get('OMEGA_URL', 'http://localhost:5000')
    context.jynb_url = os.environ.get('JUPYTER_URL', 'http://localhost:8888')
    # setup environment
    context.debug = os.environ.get('DEBUG', False)
    defaults = settings()
    context.om = om.setup()


def after_step(context, step):
    context.screenshotfn = os.path.join(context.screenshot_path, step.name + '.png')
    context.browser.screenshot(context.screenshotfn)


def after_scenario(context, scenario):
    for omstore in (context.om.datasets, context.om.jobs):
        [omstore.drop(name) for name in omstore.list()]
