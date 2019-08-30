# -- FILE: features/environment.py
# CONTAINS: Browser fixture setup and teardown
import os
from behave import fixture, use_fixture
from splinter.browser import Browser

from omegaee.features.util import get_admin_secrets, istrue, clear_om
from omegaml import settings

@fixture
def splinter_browser(context):
    headless = istrue(os.environ.get('CHROME_HEADLESS'))
    screenshot_path = os.environ.get('CHROME_SCREENSHOTS', '/tmp')
    options = None
    if headless:
        from selenium.webdriver import ChromeOptions
        print("Running headless, debug at http://localhost:9222")
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
    # get browser
    context.headless = istrue(os.environ.get('LIVETEST_HEADLESS'))
    use_fixture(splinter_browser, context)
    # set url and admin password
    context.web_url = os.environ.get('OMEGA_URL', 'https://omegaml.omegaml.io')
    admin_user, admin_password = get_admin_secrets(context.web_url)
    context.admin_user = os.environ.get('OMEGA_ADMIN_USER') or admin_user
    context.admin_password = os.environ.get('OMEGA_ADMIN_PASSWORD') or admin_password
    # setup environment
    context.debug = os.environ.get('BEHAVE_DEBUG', False)
    defaults = settings()
    defaults.OMEGA_AUTH_ENV = 'omegacommon.auth.OmegaSecureAuthenticationEnv'
    context.browser.visit(context.web_url)
    context.nbfiles = os.environ.get('BEHAVE_NBFILES', './docs/source/nb')

def after_step(context, step):
    context.screenshotfn = os.path.join(context.screenshot_path, step.name + '.png')
    context.browser.screenshot(context.screenshotfn)
    if context.debug and step.status == "failed":
        # -- ENTER DEBUGGER: Zoom in on failure location.
        # NOTE: Use IPython debugger, same for pdb (basic python debugger).
        import ipdb
        ipdb.post_mortem(step.exc_traceback)

def after_scenario(context, scenario):
    try:
        if hasattr(context, 'om'):
            clear_om(context.om)
        if hasattr(context.feature, 'om'):
            clear_om(context.feature.om)
        if hasattr(scenario, 'om'):
            clear_om(scenario.om)
    except:
        if context.debug:
            import ipdb
            ipdb.post_mortem()

