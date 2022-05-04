import re
from time import sleep

from behave import *

from omegaee.features.util import uri, find_user_apikey, handle_alert
from omegaml.tests.features.util import jburl


@then('we confirm the account')
def given_new_user(ctx):
    br = ctx.browser
    br.visit(uri(br, '/admin/post_office/email/'))
    # select email
    el = br.find_by_text(ctx.feature.username)
    el.find_by_xpath('../th[@class="field-truncated_message_id"]/a').click()
    # read confirmation url
    text = br.find_by_css('div.readonly pre').text
    regex = r".*go.to.(.*)"
    # signout of admin
    br.visit(uri(br, '/admin/logout/'))
    # execution formation
    confirm_url = re.findall(regex, text)[0]
    br.visit(confirm_url)
    assert br.is_text_present('Confirm E-mail Address', wait_time=15)
    br.find_by_text('Confirm').click()
    assert br.is_text_present('Login', wait_time=2)


@when('we log in')
def login_new_user(ctx):
    br = ctx.browser
    br.visit(uri(br, '/accounts/login'))
    assert hasattr(ctx.feature, 'username'), "feature.username is not set, did you run tag=@always?"
    br.fill('login', ctx.feature.username)
    br.fill('password', ctx.feature.password)
    br.click_link_by_text('Login ')


@then('the site shows the dashboard')
def site_shows_dashboard(ctx):
    br = ctx.browser
    assert br.is_text_present('Your apps', wait_time=15)
    assert br.is_text_present('omegaml')


@then('we log out')
def log_out(ctx):
    br = ctx.browser
    # logout from jupyter
    if getattr(ctx.feature, 'jynb_url', None):
        br.visit(ctx.feature.jynb_url)
        sleep(2)
        br.visit(uri(br, '/hub/logout'))
        sleep(2)
        br.visit(ctx.feature.jynb_url)
    # logout from web
    br.visit(ctx.web_url)
    handle_alert(br)
    br.visit(uri(br, '/accounts/logout'))
    handle_alert(br)
    for el in br.find_by_text('Sign Out'):
        el.click()
    assert br.is_text_present('sign in', wait_time=5)


@then('we can get an omega instance')
def get_omgega_instance(ctx):
    import omegaml as om
    br = ctx.browser
    # check we can get a new omegaml instance
    userid, apikey = find_user_apikey(br)
    # view = False => get a setup with public URLs
    om = om.setup(userid, apikey, api_url=ctx.web_url, view=False)
    ctx.feature.om_userid = userid
    ctx.feature.om_apikey = apikey
    ctx.feature.om = om
    assert om.datasets.mongodb is not None
    # check it actually works
    [om.datasets.drop(ds) for ds in om.datasets.list()]
    assert len(om.datasets.list()) == 0
    om.datasets.put({'foo': 'bar'}, 'test')
    assert len(om.datasets.list()) == 1
    data = om.datasets.get('test')
    assert data[0] == {'foo': 'bar'}
    om.datasets.drop('test', force=True)


@given('we are not logged in')
def not_logged_in(ctx):
    br = ctx.browser
    # logout from jupyter
    if getattr(ctx.feature, 'jynb_url', None):
        br.visit(ctx.feature.jynb_url)
        sleep(2)
        handle_alert(br)
        br.visit(uri(br, '/hub/logout'))
        sleep(2)
        handle_alert(br)
        br.visit(ctx.feature.jynb_url)
        handle_alert(br)
    # logout from web
    br.visit(ctx.web_url)
    handle_alert(br)
    br.visit(uri(br, '/accounts/logout'))
    br.is_text_present('Sign Out', wait_time=15)
    for el in br.find_by_text('Sign Out'):
        el.click()
    assert br.is_text_present('sign in', wait_time=15)


@then('we can load the jupyter notebook')
def load_jupyter_notebook(ctx):
    br = ctx.browser
    assert br.is_element_present_by_text('Profile', wait_time=15)
    br.click_link_by_text('Profile')
    userid, apikey = find_user_apikey(br)
    br.click_link_by_text('Dashboard')
    el = br.find_by_text('Notebook').first
    ctx.feature.jynb_url = el['href']
    br.visit(ctx.feature.jynb_url)
    sleep(10)
    br.windows.current = br.windows[-1]
    if br.is_element_present_by_id('username_input', wait_time=30):
        br.find_by_id('username_input').first.fill(userid)
        br.find_by_id('password_input').first.fill(apikey)
        br.click_link_by_id('login_submit')
        br.visit(jburl(ctx.feature.jynb_url, userid, nbstyle='tree'))
        assert br.is_element_present_by_id('ipython-main-app', wait_time=60)
        # check that there is actually a connection
        assert not br.is_text_present('Server error: Traceback', wait_time=15)
        assert not br.is_text_present('Connection refuse', wait_time=15)


@given('we have a connection to omegaml-ee')
def ee_connection(ctx):
    # assumes we are logged in
    br = ctx.browser
    br.visit(uri(br, '/profile/user'))
    get_omgega_instance(ctx)
    assert ctx.feature.om is not None


@when('we login to jupyter notebook')
def login_to_jupyter_notebook(ctx):
    # assumes we have omegaee web open and are logged in
    load_jupyter_notebook(ctx)
