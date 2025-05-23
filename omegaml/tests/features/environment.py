# -- FILE: features/environment.py
# CONTAINS: Browser fixture setup and teardown
import nbformat
import os
from behave import fixture, use_fixture
from behave.model_core import Status
from omegaml import settings
from omegaml.tests.features.util import istrue
from omegaml.tests.util import clear_om
from selenium.webdriver import ChromeOptions
from splinter import Browser


@fixture
def splinter_browser(context):
    headless = istrue(os.environ.get('CHROME_HEADLESS'))
    screenshot_path = os.environ.get('CHROME_SCREENSHOTS', '/tmp/screenshots')
    selenium_address = os.environ.get('SELENIUM_ADDRESS')
    os.makedirs(screenshot_path, exist_ok=True)
    options = None
    if selenium_address:
        # start remote browser using selenium grid
        options = ChromeOptions()
        options.add_argument('--no-sandbox')
        # https://stackoverflow.com/a/75939337/890242
        # options.add_argument('--headless=new')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-extensions')
        # capabilities are no passed through options https://stackoverflow.com/q/76622916/890242
        options.set_capability('browserName', 'chrome')
        options.add_argument('--window-size=1024,768')
        context.browser = Browser('remote',
                                  browser='Chrome',
                                  command_executor=selenium_address,
                                  options=options)
    else:
        # start local browser
        if headless:
            print("Running headless, debug at chrome://inspect/#devices")
            options = ChromeOptions()
            options.add_argument('--no-sandbox')
            # https://stackoverflow.com/a/75939337/890242
            options.add_argument('--headless=new')
            options.add_argument('--disable-gpu')
            options.add_argument('--remote-debugging-port=4444')
            options.add_argument('--remote-debugging-address=localhost')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-extensions')
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
    context.debug = os.environ.get('BEHAVE_DEBUG', False)
    defaults = settings()
    context.om = om.setup()
    context.nbfiles = os.environ.get('BEHAVE_NBFILES', './docs/source/reference/nb')


def before_scenario(context, scenario):
    # FIXME we do this because context.feature is set dynamically in EE testing
    context.feature.jynb_url = context.jynb_url


def after_step(context, step):
    clean_stepname = step.name.replace('.', '_').replace('/', '_')
    context.screenshotfn = os.path.join(context.screenshot_path, clean_stepname + '.png')
    context.browser.screenshot(context.screenshotfn)
    if context.debug and step.status in (Status.failed, "failed"):
        # -- ENTER DEBUGGER: Zoom in on failure location.
        # NOTE: Use IPython debugger, same for pdb (basic python debugger).
        import ipdb
        ipdb.post_mortem(step.exc_traceback)
    # also copy notebooks for debugging
    for nbname in context.om.jobs.list():
        try:
            nb = context.om.jobs.get(nbname)
            if nb is not None:
                outname = os.path.join(context.screenshot_path, nbname)
                dirname = os.path.dirname(outname)
                os.makedirs(dirname, exist_ok=True)
                nbformat.write(nb, outname)
        except Exception as e:
            print("WARNING could not write {nbname} to {outname}, got {e}".format(**locals()))


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
