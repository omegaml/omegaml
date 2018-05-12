# -- FILE: features/environment.py
# CONTAINS: Browser fixture setup and teardown
from behave import fixture, use_fixture
from splinter.browser import Browser

@fixture
def splinter_browser(context):
    context.browser = Browser('chrome')
    yield context.browser
    context.browser.quit()

def before_all(context):
    use_fixture(splinter_browser, context)