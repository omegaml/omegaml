# -- FILE: features/environment.py
# CONTAINS: Browser fixture setup and teardown
import os
from unittest import TestCase

import nbformat
import psutil
from behave import fixture, use_fixture
from splinter.browser import Browser

from omegaee.features.util import get_admin_secrets, istrue
from omegaml import settings
from omegaml.tests.util import clear_om


@fixture
def splinter_browser(context):
    from selenium.webdriver import ChromeOptions

    headless = istrue(os.environ.get('CHROME_HEADLESS'))
    screenshot_path = os.environ.get('CHROME_SCREENSHOTS', '/tmp/screenshots')
    debugging_port = os.environ.get('CHROME_DEBUGPORT', '9222')
    assert not int(debugging_port) in [i.laddr.port for i in psutil.net_connections()], f"{debugging_port} is already in use. Set --debugport or CHROME_DEBUGPORT"
    os.makedirs(screenshot_path, exist_ok=True)
    options = ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-setuid-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=800,600')
    options.add_argument(f'--remote-debugging-port={debugging_port}')
    options.add_argument('--remote-debugging-address=0.0.0.0')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-extensions')
    options.add_argument('--verbose')
    if headless:
        print(f"Running headless, debug at chrome://inspect/#devices")
        print(f"be sure to configure Discovering network targets, add http://localhost:{debugging_port}")
        options.add_argument('--headless')
    context.browser = Browser('chrome', options=options)
    context.browser.driver.set_window_size(1024, 768)
    context.screenshot_path = screenshot_path
    yield context.browser
    context.browser.quit()


def before_all(context):
    # get browser
    context.headless = istrue(os.environ.get('CHROME_HEADLESS'))
    use_fixture(splinter_browser, context)
    # set url and admin password
    context.web_url = os.environ.get('OMEGA_URL', 'https://hub.omegaml.io')
    admin_user, admin_password = get_admin_secrets(scope=context.web_url,
                                                   keys=['admin_user', 'admin_password'])
    context.admin_user = os.environ.get('OMEGA_ADMIN_USER') or admin_user
    context.admin_password = os.environ.get('OMEGA_ADMIN_PASSWORD') or admin_password
    context.api_user = os.environ.get('OMEGA_APIUSER') or admin_user.split('@')[0]
    context.api_key = os.environ.get('OMEGA_APIKEY') or admin_password
    # setup environment
    context.debug = os.environ.get('BEHAVE_DEBUG', False)
    defaults = settings()
    defaults.OMEGA_AUTH_ENV = 'omegaml.client.auth.CloudClientAuthenticationEnv'
    context.browser.visit(context.web_url)
    context.nbfiles = os.environ.get('BEHAVE_NBFILES', './docs/source/nb')
    # setup test assertion methods
    # -- so we can use ctx.assertEqual, ctx.assertIn etc. just as with tests
    tc = TestCase()
    for m in dir(tc):
        if m.startswith('assert'):
            setattr(context, m, getattr(tc, m))


def after_step(context, step):
    clean_stepname = step.name.replace('.', '_').replace('/', '_')
    context.screenshotfn = os.path.join(context.screenshot_path, clean_stepname + '.png')
    context.browser.screenshot(context.screenshotfn)
    if context.debug and step.status == "failed":
        # -- ENTER DEBUGGER: Zoom in on failure location.
        # NOTE: Use IPython debugger, same for pdb (basic python debugger).
        import ipdb
        ipdb.post_mortem(step.exc_traceback)

    # also copy notebooks for debugging
    om = get_om(context)
    if om:
        copy_notebooks(om, context)
        keep_omuserkeys(om, context)


def after_scenario(context, scenario):
    try:
        om = get_om(context)
        if om:
            clear_om(om)
    except:
        if context.debug:
            import ipdb
            ipdb.post_mortem()


def get_om(context):
    om = None
    try:
        oms = [getattr(c, 'om', None) for c in (context, context.feature, context.scenario)
               if getattr(c, 'om', None) is not None]
        if oms:
            om = oms[-1]
    except:
        pass
    return om


def copy_notebooks(om, context):
    for nbname in om.jobs.list():
        try:
            nb = om.jobs.get(nbname)
            if nb is not None:
                dirname = os.path.join(context.screenshot_path, os.path.dirname(nbname))
                fname = os.path.join(context.screenshot_path, nbname)
                os.makedirs(dirname, exist_ok=True)
                nbformat.write(nb, fname)
        except:
            print("WARNING could not write {nbname}".format(**locals()))
            if context.debug:
                import ipdb
                ipdb.post_mortem()


def keep_omuserkeys(om, context):
    fn = os.path.join(context.screenshot_path, 'test_secrets.txt')
    if hasattr(context.feature, 'om_userid'):
        with open(fn, 'a') as fout:
            entry = '{}:{} {}\n'.format(context.feature.om_userid,
                                        context.feature.om_apikey, repr(om))
            fout.write(entry)
